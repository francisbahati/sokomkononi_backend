# ============================================================
# apps/deals/views.py
# ============================================================

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status, viewsets

from rest_framework.decorators import action

from rest_framework.exceptions import ValidationError

from rest_framework.response import Response

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from apps.listings.models import Listing

from .models import DealRoom, NegotiationOffer

from .permissions import (
    IsDealParticipant,
    IsVerifiedDealUser,
)

from .serializers import (
    DealRoomAcceptOfferSerializer,
    DealRoomCancelSerializer,
    DealRoomCreateSerializer,
    DealRoomDetailSerializer,
    DealRoomListSerializer,
    NegotiationOfferCreateSerializer,
    NegotiationOfferSerializer,
)

from .services.notifications import (
    notify_deal_room_cancelled,
    notify_deal_room_created,
    notify_new_offer,
    notify_offer_accepted,
)


# ============================================================================
# DEAL ROOM VIEWSET
# ============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Orodhesha Deal Rooms",
        description=(
            "Inaonyesha Deal Rooms ambazo mtumiaji aliyeingia "
            "ni buyer au seller. Admin anaweza kuona Deal Rooms zote."
        ),
        responses={
            200: DealRoomListSerializer(many=True),
        },
    ),
    retrieve=extend_schema(
        summary="Angalia Deal Room",
        description=(
            "Inaonyesha taarifa kamili za Deal Room pamoja na "
            "historia yote ya offers."
        ),
        responses={
            200: DealRoomDetailSerializer,
            404: OpenApiResponse(
                description="Deal Room haijapatikana.",
            ),
        },
    ),
    create=extend_schema(
        summary="Anza Kununua / Tengeneza Deal Room",
        description=(
            "Mnunuzi aliye na akaunti iliyothibitishwa anaweza "
            "kuanzisha Deal Room kwenye tangazo AVAILABLE. "
            "Huwezi kuanzisha Deal Room kwenye tangazo lako mwenyewe."
        ),
        request=DealRoomCreateSerializer,
        responses={
            201: DealRoomDetailSerializer,
            400: OpenApiResponse(
                description="Taarifa si sahihi au tangazo haliwezi kununuliwa.",
            ),
        },
        examples=[
            OpenApiExample(
                "Mfano wa kuanzisha Deal Room",
                value={
                    "listing_id": 1,
                },
                request_only=True,
            ),
        ],
    ),
)
class DealRoomViewSet(viewsets.ModelViewSet):
    """
    API ya Deal Rooms.

    Buyer na seller wanaweza kufikia Deal Room zao.

    Admin anaweza kuziona zote kwa ajili ya moderation/disputes.
    """

    queryset = (
        DealRoom.objects
        .select_related(
            "listing",
            "listing__category",
            "buyer",
            "seller",
        )
        .prefetch_related(
            "offers",
            "offers__offered_by",
        )
        .all()
    )

    http_method_names = [
        "get",
        "post",
        "head",
        "options",
    ]

    def get_serializer_class(self):
        if self.action == "create":
            return DealRoomCreateSerializer

        if self.action in [
            "retrieve",
            "offer",
            "accept_offer",
            "cancel",
        ]:
            if self.action == "offer":
                return NegotiationOfferCreateSerializer

            if self.action == "accept_offer":
                return DealRoomAcceptOfferSerializer

            if self.action == "cancel":
                return DealRoomCancelSerializer

            return DealRoomDetailSerializer

        return DealRoomListSerializer

    def get_permissions(self):
        if self.action == "create":
            return [
                permissions.IsAuthenticated(),
                IsVerifiedDealUser(),
            ]

        if self.action in [
            "retrieve",
            "offer",
            "accept_offer",
            "cancel",
        ]:
            return [
                permissions.IsAuthenticated(),
                IsVerifiedDealUser(),
                IsDealParticipant(),
            ]

        return [
            permissions.IsAuthenticated(),
            IsVerifiedDealUser(),
        ]

    # ========================================================================
    # LIST
    # ========================================================================

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if user.is_staff:
            return queryset

        return queryset.filter(
            Q(buyer=user) | Q(seller=user)
        )

    # ========================================================================
    # CREATE DEAL ROOM
    # ========================================================================

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={
                "request": request,
            },
        )

        serializer.is_valid(raise_exception=True)

        try:
            deal_room = serializer.save()

        except IntegrityError:
            existing = (
                DealRoom.objects
                .select_related(
                    "listing",
                    "listing__category",
                    "buyer",
                    "seller",
                )
                .filter(
                    listing_id=serializer.validated_data["listing_id"],
                    buyer=request.user,
                )
                .first()
            )

            if existing:
                raise ValidationError(
                    {
                        "listing_id": (
                            f"Deal Room tayari ipo. "
                            f"Deal Room ID: {existing.id}"
                        )
                    }
                )

            raise

        notify_deal_room_created(
            deal_room=deal_room,
        )

        response_serializer = DealRoomDetailSerializer(
            deal_room,
            context={
                "request": request,
            },
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    # ========================================================================
    # RETRIEVE
    # ========================================================================

    def retrieve(self, request, *args, **kwargs):
        deal_room = self.get_object()

        serializer = DealRoomDetailSerializer(
            deal_room,
            context={
                "request": request,
            },
        )

        return Response(serializer.data)

    # ========================================================================
    # SEND OFFER / COUNTER-OFFER
    # ========================================================================

    @extend_schema(
        summary="Tuma Offer / Counter-offer",
        description=(
            "Buyer au seller anaweza kutuma offer mpya kwenye Deal Room. "
            "Ikiwa offer hii inajibu offer ya upande mwingine, offer ya "
            "awali itawekwa COUNTERED. Offer ya kwanza itabadilisha "
            "Deal Room kutoka OPEN kwenda NEGOTIATING."
        ),
        request=NegotiationOfferCreateSerializer,
        responses={
            201: NegotiationOfferSerializer,
            400: OpenApiResponse(
                description="Offer haiwezi kutumwa.",
            ),
        },
        examples=[
            OpenApiExample(
                "Offer ya kwanza",
                value={
                    "amount": "85000000.00",
                    "message": "Ninaweza kulipa TZS 85,000,000.",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Counter-offer",
                value={
                    "amount": "92000000.00",
                    "message": "Bei yangu ya mwisho ni TZS 92,000,000.",
                    "responded_to": 1,
                },
                request_only=True,
            ),
        ],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="offers",
        url_name="offers",
    )
    @transaction.atomic
    def offer(self, request, pk=None):
        deal_room = self.get_object()

        if deal_room.status not in [
            DealRoom.Status.OPEN,
            DealRoom.Status.NEGOTIATING,
        ]:
            return Response(
                {
                    "detail": (
                        "Deal Room hii haipokei offers mpya. "
                        f"Hali ya sasa ni {deal_room.status}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = NegotiationOfferCreateSerializer(
            data=request.data,
            context={
                "request": request,
                "deal_room": deal_room,
            },
        )

        serializer.is_valid(raise_exception=True)

        responded_to_id = serializer.validated_data.get(
            "responded_to"
        )

        if request.user.id == deal_room.buyer_id:
            offered_by = NegotiationOffer.OfferedBy.BUYER

        elif request.user.id == deal_room.seller_id:
            offered_by = NegotiationOffer.OfferedBy.SELLER

        else:
            return Response(
                {
                    "detail": (
                        "Huruhusiwi kutuma offer kwenye Deal Room hii."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        responded_to = None

        if responded_to_id:
            responded_to = (
                NegotiationOffer.objects
                .select_for_update()
                .filter(
                    pk=responded_to_id,
                    deal_room=deal_room,
                )
                .first()
            )

            if not responded_to:
                raise ValidationError(
                    {
                        "responded_to": (
                            "Offer uliyochagua haijapatikana."
                        )
                    }
                )

            if responded_to.offered_by_id == request.user.id:
                raise ValidationError(
                    {
                        "responded_to": (
                            "Huwezi kujibu offer yako mwenyewe."
                        )
                    }
                )

            if responded_to.status != NegotiationOffer.Status.PENDING:
                raise ValidationError(
                    {
                        "responded_to": (
                            "Offer hii haipo kwenye hali ya PENDING."
                        )
                    }
                )

            responded_to.status = NegotiationOffer.Status.COUNTERED

            responded_to.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        new_offer = NegotiationOffer.objects.create(
            deal_room=deal_room,
            offered_by=request.user,
            amount=serializer.validated_data["amount"],
            message=serializer.validated_data.get(
                "message",
                "",
            ),
            status=NegotiationOffer.Status.PENDING,
            responded_to=responded_to,
        )

        if deal_room.status == DealRoom.Status.OPEN:
            deal_room.status = DealRoom.Status.NEGOTIATING

            deal_room.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        notify_new_offer(
            deal_room=deal_room,
            offer=new_offer,
        )

        response_serializer = NegotiationOfferSerializer(
            new_offer,
            context={
                "request": request,
            },
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    # ========================================================================
    # ACCEPT OFFER
    # ========================================================================

    @extend_schema(
        summary="Kubali Offer",
        description=(
            "Buyer au seller anaweza kukubali offer ya upande mwingine. "
            "Offer iliyokubaliwa itaweka agreed_price na Deal Room "
            "itabadilika kuwa AGREED. Offers nyingine zote za PENDING "
            "zitawekwa REJECTED. Listing itawekwa RESERVED."
        ),
        request=DealRoomAcceptOfferSerializer,
        responses={
            200: DealRoomDetailSerializer,
            400: OpenApiResponse(
                description="Offer haiwezi kukubaliwa.",
            ),
        },
        examples=[
            OpenApiExample(
                "Kubali offer",
                value={
                    "offer_id": 2,
                },
                request_only=True,
            ),
        ],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="accept-offer",
        url_name="accept-offer",
    )
    @transaction.atomic
    def accept_offer(self, request, pk=None):

        deal_room = get_object_or_404(
            DealRoom.objects
            .select_for_update()
            .select_related(
                "listing",
                "listing__category",
                "buyer",
                "seller",
            ),
            pk=pk,
        )

        self.check_object_permissions(request, deal_room)

        if deal_room.status not in [
            DealRoom.Status.OPEN,
            DealRoom.Status.NEGOTIATING,
        ]:
            return Response(
                {
                    "detail": (
                        "Deal Room hii haiwezi kukubali offer. "
                        f"Hali ya sasa ni {deal_room.status}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DealRoomAcceptOfferSerializer(
            data=request.data,
            context={
                "request": request,
                "deal_room": deal_room,
            },
        )

        serializer.is_valid(raise_exception=True)

        offer_id = serializer.validated_data["offer_id"]

        offer = (
            NegotiationOffer.objects
            .select_for_update()
            .select_related("offered_by")
            .filter(
                pk=offer_id,
                deal_room=deal_room,
            )
            .first()
        )

        if not offer:
            raise ValidationError(
                {
                    "offer_id": (
                        "Offer haijapatikana kwenye Deal Room hii."
                    )
                }
            )

        if offer.offered_by_id == request.user.id:
            raise ValidationError(
                {
                    "offer_id": (
                        "Huwezi kukubali offer yako mwenyewe."
                    )
                }
            )

        if offer.status != NegotiationOffer.Status.PENDING:
            raise ValidationError(
                {
                    "offer_id": (
                        "Offer hii haiwezi kukubaliwa kwa sababu "
                        "hali yake si PENDING."
                    )
                }
            )

        offer.status = NegotiationOffer.Status.ACCEPTED

        offer.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        (
            NegotiationOffer.objects
            .filter(
                deal_room=deal_room,
                status=NegotiationOffer.Status.PENDING,
            )
            .exclude(pk=offer.pk)
            .update(
                status=NegotiationOffer.Status.REJECTED,
                updated_at=timezone.now(),
            )
        )

        deal_room.status = DealRoom.Status.AGREED
        deal_room.agreed_price = offer.amount
        deal_room.agreed_at = timezone.now()

        deal_room.save(
            update_fields=[
                "status",
                "agreed_price",
                "agreed_at",
                "updated_at",
            ]
        )

        listing = deal_room.listing

        if listing.status == Listing.Status.AVAILABLE:
            listing.status = Listing.Status.RESERVED

            listing.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        notify_offer_accepted(
            deal_room=deal_room,
            offer=offer,
        )

        response_serializer = DealRoomDetailSerializer(
            deal_room,
            context={
                "request": request,
            },
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    # ========================================================================
    # CANCEL DEAL ROOM
    # ========================================================================

    @extend_schema(
        summary="Funga Deal Room",
        description=(
            "Buyer au seller anaweza kufunga Deal Room kabla ya "
            "makubaliano ya mwisho. Deal Room iliyofikia AGREED "
            "haiwezi kufutwa kupitia endpoint hii."
        ),
        request=DealRoomCancelSerializer,
        responses={
            200: DealRoomDetailSerializer,
            400: OpenApiResponse(
                description="Deal Room haiwezi kufungwa.",
            ),
        },
        examples=[
            OpenApiExample(
                "Mfano",
                value={
                    "reason": "Hatukufikia makubaliano ya bei.",
                },
                request_only=True,
            ),
        ],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="cancel",
        url_name="cancel",
    )
    @transaction.atomic
    def cancel(self, request, pk=None):

        deal_room = get_object_or_404(
            DealRoom.objects
            .select_for_update()
            .select_related(
                "listing",
                "listing__category",
                "buyer",
                "seller",
            ),
            pk=pk,
        )

        self.check_object_permissions(request, deal_room)

        if deal_room.status not in [
            DealRoom.Status.OPEN,
            DealRoom.Status.NEGOTIATING,
        ]:
            return Response(
                {
                    "detail": (
                        "Deal Room hii haiwezi kufungwa. "
                        f"Hali ya sasa ni {deal_room.status}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DealRoomCancelSerializer(
            data=request.data,
            context={
                "request": request,
                "deal_room": deal_room,
            },
        )

        serializer.is_valid(raise_exception=True)

        cancellation_reason = serializer.validated_data.get(
            "reason",
            "",
        )

        deal_room.status = DealRoom.Status.CANCELLED

        deal_room.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        (
            NegotiationOffer.objects
            .filter(
                deal_room=deal_room,
                status=NegotiationOffer.Status.PENDING,
            )
            .update(
                status=NegotiationOffer.Status.CANCELLED,
                updated_at=timezone.now(),
            )
        )

        notify_deal_room_cancelled(
            deal_room=deal_room,
            cancelled_by=request.user,
            reason=cancellation_reason,
        )

        response_serializer = DealRoomDetailSerializer(
            deal_room,
            context={
                "request": request,
            },
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )