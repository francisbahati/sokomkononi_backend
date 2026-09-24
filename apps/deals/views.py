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
from .permissions import IsDealParticipant, IsVerifiedDealUser
from .serializers_admin import AdminDealRoomSerializer
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
    notify_offer_rejected,
)


@extend_schema_view(
    list=extend_schema(responses={200: DealRoomListSerializer(many=True)}),
    retrieve=extend_schema(responses={200: DealRoomDetailSerializer}),
    create=extend_schema(
        request=DealRoomCreateSerializer,
        responses={201: DealRoomDetailSerializer},
    ),
)
class DealRoomViewSet(viewsets.ModelViewSet):
    queryset = (
        DealRoom.objects
        .select_related(
            "listing", "listing__category", "buyer", "seller",
        )
        .prefetch_related("offers", "offers__offered_by")
    )

    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return DealRoomCreateSerializer
        if self.action == "offer":
            return NegotiationOfferCreateSerializer
        if self.action == "accept_offer":
            return DealRoomAcceptOfferSerializer
        if self.action == "cancel":
            return DealRoomCancelSerializer
        if self.action == "retrieve":
            if self.request.user.is_staff:
                return AdminDealRoomSerializer
            return DealRoomDetailSerializer
        if self.request.user.is_staff:
            return AdminDealRoomSerializer
        return DealRoomListSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsVerifiedDealUser()]
        if self.action in ["retrieve", "offer", "accept_offer", "cancel"]:
            return [
                permissions.IsAuthenticated(),
                IsVerifiedDealUser(),
                IsDealParticipant(),
            ]
        return [permissions.IsAuthenticated(), IsVerifiedDealUser()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_staff:
            return qs
        return qs.filter(Q(buyer=user) | Q(seller=user))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                deal_room = serializer.save()
        except IntegrityError:
            existing = DealRoom.objects.filter(
                listing_id=serializer.validated_data["listing_id"],
                buyer=request.user,
            ).first()
            if existing:
                raise ValidationError({
                    "listing_id": (
                        f"Deal Room tayari ipo. Deal Room ID: {existing.id}"
                    )
                })
            raise

        notify_deal_room_created(deal_room=deal_room)

        # Auto-create a Lead for the seller
        try:
            from apps.leads.services.lead import upsert_lead_from_deal_room
            upsert_lead_from_deal_room(deal_room)
        except Exception:
            pass

        response_serializer = DealRoomDetailSerializer(
            deal_room, context={"request": request},
        )
        return Response(
            response_serializer.data, status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        deal_room = self.get_object()
        serializer = DealRoomDetailSerializer(
            deal_room, context={"request": request},
        )
        return Response(serializer.data)

    @extend_schema(
        request=NegotiationOfferCreateSerializer,
        responses={201: NegotiationOfferSerializer},
    )
    @action(detail=True, methods=["post"], url_path="offers", url_name="offers")
    @transaction.atomic
    def offer(self, request, pk=None):
        deal_room = self.get_object()

        if deal_room.status not in [
            DealRoom.Status.OPEN, DealRoom.Status.NEGOTIATING,
        ]:
            return Response(
                {
                    "detail": (
                        "Deal Room hii haipokei offers mpya. "
                        f"Hali ya sasa ni {deal_room.status}."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = NegotiationOfferCreateSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)

        responded_to_id = serializer.validated_data.get("responded_to")
        responded_to = None

        if responded_to_id:
            responded_to = (
                NegotiationOffer.objects
                .select_for_update()
                .filter(pk=responded_to_id, deal_room=deal_room)
                .first()
            )

            if not responded_to:
                raise ValidationError({
                    "responded_to": "Offer uliyochagua haijapatikana."
                })

            if responded_to.offered_by_id == request.user.id:
                raise ValidationError({
                    "responded_to": "Huwezi kujibu offer yako mwenyewe."
                })

            if responded_to.status != NegotiationOffer.Status.PENDING:
                raise ValidationError({
                    "responded_to": "Offer hii haipo kwenye hali ya PENDING."
                })

            responded_to.status = NegotiationOffer.Status.COUNTERED
            responded_to.save(update_fields=["status", "updated_at"])

        new_offer = NegotiationOffer.objects.create(
            deal_room=deal_room,
            offered_by=request.user,
            amount=serializer.validated_data["amount"],
            message=serializer.validated_data.get("message", ""),
            status=NegotiationOffer.Status.PENDING,
            responded_to=responded_to,
        )

        if deal_room.status == DealRoom.Status.OPEN:
            deal_room.status = DealRoom.Status.NEGOTIATING
            deal_room.save(update_fields=["status", "updated_at"])
        else:
            deal_room.save(update_fields=["updated_at"])

        notify_new_offer(deal_room=deal_room, offer=new_offer)

        # Update the lead message count for this buyer/listing pair
        try:
            from apps.leads.services.lead import upsert_lead_from_deal_room
            upsert_lead_from_deal_room(deal_room)
        except Exception:
            pass

        return Response(
            NegotiationOfferSerializer(
                new_offer, context={"request": request, "deal_room": deal_room},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=DealRoomAcceptOfferSerializer,
        responses={200: DealRoomDetailSerializer},
    )
    @action(
        detail=True, methods=["post"],
        url_path="accept-offer", url_name="accept-offer",
    )
    @transaction.atomic
    def accept_offer(self, request, pk=None):
        deal_room = get_object_or_404(
            DealRoom.objects
            .select_for_update()
            .select_related("listing", "listing__category", "buyer", "seller"),
            pk=pk,
        )
        self.check_object_permissions(request, deal_room)

        if deal_room.status not in [
            DealRoom.Status.OPEN, DealRoom.Status.NEGOTIATING,
        ]:
            return Response(
                {
                    "detail": (
                        "Deal Room hii haiwezi kukubali offer. "
                        f"Hali ya sasa ni {deal_room.status}."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DealRoomAcceptOfferSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)

        offer_id = serializer.validated_data["offer_id"]
        offer = (
            NegotiationOffer.objects
            .select_for_update()
            .select_related("offered_by")
            .filter(pk=offer_id, deal_room=deal_room)
            .first()
        )

        if not offer:
            raise ValidationError({
                "offer_id": "Offer haijapatikana kwenye Deal Room hii."
            })

        if offer.offered_by_id == request.user.id:
            raise ValidationError({
                "offer_id": "Huwezi kukubali offer yako mwenyewe."
            })

        if offer.status != NegotiationOffer.Status.PENDING:
            raise ValidationError({
                "offer_id": (
                    "Offer hii haiwezi kukubaliwa kwa sababu hali yake "
                    "si PENDING."
                ),
            })

        # Mark accepted
        offer.status = NegotiationOffer.Status.ACCEPTED
        offer.save(update_fields=["status", "updated_at"])

        # Reject remaining pending siblings
        siblings_pending = NegotiationOffer.objects.filter(
            deal_room=deal_room,
            status=NegotiationOffer.Status.PENDING,
        ).exclude(pk=offer.pk)

        sibling_list = list(siblings_pending)
        siblings_pending.update(
            status=NegotiationOffer.Status.REJECTED,
            updated_at=timezone.now(),
        )

        deal_room.status = DealRoom.Status.AGREED
        deal_room.agreed_price = offer.amount
        deal_room.agreed_at = timezone.now()
        deal_room.save(update_fields=[
            "status", "agreed_price", "agreed_at", "updated_at",
        ])

        listing = deal_room.listing
        if listing.status == Listing.Status.AVAILABLE:
            listing.status = Listing.Status.RESERVED
            listing.save(update_fields=["status", "updated_at"])

        # Cancel sibling Deal Rooms for the same listing
        sibling_rooms = (
            DealRoom.objects
            .select_for_update()
            .filter(
                listing=deal_room.listing,
                status__in=[
                    DealRoom.Status.OPEN,
                    DealRoom.Status.NEGOTIATING,
                ],
            )
            .exclude(pk=deal_room.pk)
        )

        sibling_room_list = list(sibling_rooms)
        sibling_rooms.update(
            status=DealRoom.Status.CANCELLED,
            updated_at=timezone.now(),
        )

        for sib in sibling_room_list:
            sib.offers.filter(
                status=NegotiationOffer.Status.PENDING,
            ).update(
                status=NegotiationOffer.Status.CANCELLED,
                updated_at=timezone.now(),
            )
            notify_deal_room_cancelled(
                deal_room=sib,
                cancelled_by=request.user,
                reason="Tangazo limeshachukuliwa na mnunuzi mwingine.",
            )

        notify_offer_accepted(deal_room=deal_room, offer=offer)

        for rejected in sibling_list:
            notify_offer_rejected(deal_room=deal_room, offer=rejected)

        return Response(
            DealRoomDetailSerializer(
                deal_room, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=DealRoomCancelSerializer,
        responses={200: DealRoomDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="cancel", url_name="cancel")
    @transaction.atomic
    def cancel(self, request, pk=None):
        deal_room = get_object_or_404(
            DealRoom.objects
            .select_for_update()
            .select_related("listing", "listing__category", "buyer", "seller"),
            pk=pk,
        )
        self.check_object_permissions(request, deal_room)

        if deal_room.status not in [
            DealRoom.Status.OPEN, DealRoom.Status.NEGOTIATING,
        ]:
            return Response(
                {
                    "detail": (
                        "Deal Room hii haiwezi kufungwa. "
                        f"Hali ya sasa ni {deal_room.status}."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DealRoomCancelSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)

        cancellation_reason = serializer.validated_data.get("reason", "")

        deal_room.status = DealRoom.Status.CANCELLED
        deal_room.save(update_fields=["status", "updated_at"])

        NegotiationOffer.objects.filter(
            deal_room=deal_room,
            status=NegotiationOffer.Status.PENDING,
        ).update(
            status=NegotiationOffer.Status.CANCELLED,
            updated_at=timezone.now(),
        )

        notify_deal_room_cancelled(
            deal_room=deal_room,
            cancelled_by=request.user,
            reason=cancellation_reason,
        )

        return Response(
            DealRoomDetailSerializer(
                deal_room, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )