# ============================================================
# apps/listings/views.py
# ============================================================

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, F
from django.shortcuts import get_object_or_404
from django.utils import timezone

from django_filters.rest_framework import DjangoFilterBackend

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView

from apps.core.mixins import SoftDeleteViewSetMixin
from apps.credits.services import consume_credit

from .models import (
    BusinessDetails,
    EquipmentDetails,
    LandDetails,
    Listing,
    ListingFee,
    ListingImage,
    PropertyDetails,
    VehicleDetails,
)

from .permissions import (
    IsOwnerOrAdmin,
    IsVerifiedUser,
)

from .serializers import (
    AdminPendingListingSerializer,
    BusinessDetailsSerializer,
    EquipmentDetailsSerializer,
    LandDetailsSerializer,
    ListingDetailSerializer,
    ListingFeePaymentSerializer,
    ListingFeeSerializer,
    ListingImageSerializer,
    ListingListSerializer,
    ListingRejectionSerializer,
    ListingWriteSerializer,
    PropertyDetailsSerializer,
    VehicleDetailsSerializer,
)

from .services.listing_fee import create_listing_fee

from .services.listing_moderation import (
    approve_listing,
    reject_listing,
)

from .views_helpers import require_int_listing_id

logger = logging.getLogger(__name__)

# ============================================================================
# CATEGORY SLUGS
# ============================================================================

CATEGORY_SLUGS = {
    "property": "nyumba-majengo",
    "land": "viwanja-mashamba",
    "vehicle": "magari",
    "business": "biashara-zinazouzwa",
    "equipment": "mashine-heavy-equipment",
}

# ============================================================================
# LISTING VIEWSET
# ============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Orodha ya matangazo",
        description="Huonyesha matangazo yanayopatikana.",
    ),
    retrieve=extend_schema(
        summary="Angalia tangazo",
        description="Huonyesha taarifa kamili za tangazo.",
    ),
    create=extend_schema(
        summary="Weka tangazo",
        description=(
            "Mtumiaji aliyethibitishwa anaweza kuunda tangazo. "
            "Muuzaji anawekwa moja kwa moja kutoka kwenye akaunti."
        ),
        examples=[
            OpenApiExample(
                "Mfano wa tangazo",
                value={
                    "category_id": 1,
                    "title": "Nyumba nzuri ya vyumba 4 Dar es Salaam",
                    "description": (
                        "Nyumba nzuri yenye vyumba vinne, "
                        "maegesho na huduma muhimu."
                    ),
                    "price": "350000000.00",
                    "location": "Mikocheni, Dar es Salaam",
                },
                request_only=True,
            )
        ],
    ),
    update=extend_schema(summary="Badilisha tangazo"),
    partial_update=extend_schema(summary="Badilisha sehemu ya tangazo"),
    destroy=extend_schema(
        summary="Futa/hifadhi tangazo",
        description=(
            "Tangazo huwekwa kwenye kikapu kwa siku 90. "
            "Muuzaji anaweza kulirejesha kabla ya muda kuisha. "
            "Admin anaweza kufuta kabisa kwa `?hard=true`."
        ),
    ),
    restore=extend_schema(
        summary="Rejesha tangazo",
        description=(
            "Rejesha tangazo lililofutwa (soft delete). "
            "Muuzaji anaweza kurejesha tangazo lake mwenyewe. "
            "Admin anaweza kurejesha tangazo lolote."
        ),
    ),
)
class ListingViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet):

    owner_field = "seller"
    staff_can_restore_any = True

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    filterset_fields = [
        "category",
        "status",
        "is_featured",
        "seller",
        "is_boosted",
    ]

    search_fields = [
        "title",
        "description",
        "location",
    ]

    ordering_fields = [
        "created_at",
        "price",
        "views_count",
    ]

    ordering = [F("leading_until").desc(nulls_last=True), "-created_at"]

    queryset = Listing.objects.select_related(
        "seller",
        "category",
    ).prefetch_related(
        "images",
        "property_details",
        "land_details",
        "vehicle_details",
        "business_details",
        "equipment_details",
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        public_statuses = [
            Listing.Status.AVAILABLE,
            Listing.Status.RESERVED,
            Listing.Status.SOLD,
        ]

        if not user.is_authenticated:
            return queryset.filter(status__in=public_statuses)

        if user.is_staff:
            return queryset

        return queryset.filter(
            Q(status__in=public_statuses) | Q(seller=user)
        ).distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return ListingListSerializer

        if self.action == "retrieve":
            return ListingDetailSerializer

        return ListingWriteSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [permissions.AllowAny]
        elif self.action == "create":
            permission_classes = [IsVerifiedUser]
        else:
            permission_classes = [IsOwnerOrAdmin]

        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        """
        Override create to return ListingDetailSerializer (with id) instead
        of ListingWriteSerializer (no id). Frontend needs the id to
        upload images, pay fees, etc.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        output = ListingDetailSerializer(instance, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        serializer.save(
            seller=self.request.user,
            status=Listing.Status.DRAFT,
        )

    def perform_update(self, serializer):
        instance = self.get_object()

        if self.request.user.is_staff:
            serializer.save()
            return

        serializer.save(
            seller=instance.seller,
            status=instance.status,
        )

    # ═══════════════════════════════════════════════════════════
    # DESTROY — soft delete (default) au hard delete (admin)
    # Defensive: inafuta related models zote kwa try/except.
    #
    # SASISHO: Mpangilio sahihi ili kuepuka ProtectedError:
    #   1. ListingFee (PROTECT)
    #   2. Lead (PROTECT — LAZIMA hard_delete kwa sababu Lead ni SoftDeleteModel)
    #   3. Reservation + InspectionPeriod (PROTECT kwa Transaction)
    #   4. Transaction (PROTECT kwa Listing)
    #   5. DealRoom (PROTECT kwa Listing; NegotiationOffer CASCADE)
    #   6. Related models zingine (CASCADE au soft, inatumia hard_delete)
    #   7. Details (Property/Land/Vehicle/Business/Equipment)
    #   8. listing.hard_delete()
    # ═══════════════════════════════════════════════════════════
    def destroy(self, request, *args, **kwargs):
        listing = self.get_object()

        is_hard = request.query_params.get(
            "hard", "false"
        ).lower() in ("true", "1", "yes")

        if request.user.is_staff and is_hard:
            # ══════════════════════════════════════════════════
            # HARD DELETE
            # ══════════════════════════════════════════════════

            # 1. Futa ListingFee (PROTECT)
            try:
                ListingFee.objects.filter(listing=listing).delete()
            except Exception as exc:
                logger.warning(
                    "[listings] delete ListingFee for %s failed: %s",
                    listing.id, exc,
                )

            # 2. Futa Leads (PROTECT kwa Listing) — HARD DELETE
            #    Lead ni SoftDeleteModel. `manager.all().delete()` inaita
            #    soft delete (haifuti kabisa). Tunahitaji `hard_delete()`
            #    ili `Lead.listing` FK isiondoke na kuzuia listing delete.
            try:
                from apps.leads.models import Lead
                leads_qs = Lead.objects.filter(listing=listing)
                for lead in leads_qs:
                    if hasattr(lead, "hard_delete"):
                        lead.hard_delete()
                    else:
                        lead.delete()
            except ImportError as exc:
                logger.warning(
                    "[listings] leads app not available: %s", exc,
                )
            except Exception as exc:
                logger.warning(
                    "[listings] delete Lead for %s failed: %s",
                    listing.id, exc,
                )

            # 3. Futa Transaction chain: InspectionPeriod + Reservation + Transaction
            try:
                from apps.transactions.models import (
                    Transaction,
                    Reservation,
                    InspectionPeriod,
                )

                tx_ids = list(
                    Transaction.objects
                    .filter(listing=listing)
                    .values_list("id", flat=True)
                )

                if tx_ids:
                    # 3a. InspectionPeriod kwanza (PROTECT kwa Transaction)
                    try:
                        InspectionPeriod.objects.filter(
                            transaction_id__in=tx_ids,
                        ).delete()
                    except Exception as exc:
                        logger.warning(
                            "[listings] delete InspectionPeriod for %s failed: %s",
                            listing.id, exc,
                        )

                    # 3b. Reservation (PROTECT kwa Transaction)
                    try:
                        Reservation.objects.filter(
                            transaction_id__in=tx_ids,
                        ).delete()
                    except Exception as exc:
                        logger.warning(
                            "[listings] delete Reservation for %s failed: %s",
                            listing.id, exc,
                        )

                    # 3c. Transaction (PROTECT kwa Listing)
                    try:
                        Transaction.objects.filter(
                            listing=listing,
                        ).delete()
                    except Exception as exc:
                        logger.warning(
                            "[listings] delete Transaction for %s failed: %s",
                            listing.id, exc,
                        )
            except ImportError as exc:
                logger.warning(
                    "[listings] transactions app not available: %s", exc,
                )

            # 4. Futa DealRoom (PROTECT kwa Listing; NegotiationOffer CASCADE)
            try:
                from apps.deals.models import DealRoom

                DealRoom.objects.filter(listing=listing).delete()
            except ImportError as exc:
                logger.warning(
                    "[listings] deals app not available: %s", exc,
                )
            except Exception as exc:
                logger.warning(
                    "[listings] delete DealRoom for %s failed: %s",
                    listing.id, exc,
                )

            # 5. Futa related models zingine (CASCADE au soft)
            related_fields = [
                "images",
                "boosts",
                "waiting_list_entries",
                "saved_by",
                "search_matches",
                "conversations",
                "banner_ads",
                "leading_purchases",
            ]

            for field_name in related_fields:
                try:
                    manager = getattr(listing, field_name, None)
                    if manager is None:
                        continue
                    for obj in manager.all():
                        if hasattr(obj, "hard_delete"):
                            obj.hard_delete()
                        else:
                            obj.delete()
                except Exception as exc:
                    logger.warning(
                        "[listings] delete %s for listing %s failed: %s",
                        field_name, listing.id, exc,
                    )

            # 6. Futa details (Property/Land/Vehicle/Business/Equipment)
            detail_fields = [
                "property_details",
                "land_details",
                "vehicle_details",
                "business_details",
                "equipment_details",
            ]
            for field_name in detail_fields:
                try:
                    obj = getattr(listing, field_name, None)
                    if obj is not None:
                        obj.delete()
                except Exception as exc:
                    logger.warning(
                        "[listings] delete %s for listing %s failed: %s",
                        field_name, listing.id, exc,
                    )

            # 7. Sasa hard delete
            try:
                listing.hard_delete()
            except Exception as exc:
                logger.error(
                    "[listings] hard_delete failed for %s: %s",
                    listing.id, exc,
                )
                return Response(
                    {"detail": f"Imeshindwa kufuta: {exc}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {"detail": "Tangazo limefutwa kabisa."},
                status=status.HTTP_204_NO_CONTENT,
            )

        # ── Soft delete (default) ─────────────────────────────
        listing.delete(
            by=request.user,
            reason=request.data.get("reason", "") if isinstance(
                request.data, dict
            ) else "",
        )

        return Response(
            {
                "detail": (
                    "Tangazo limewekwa kwenye kikapu. "
                    "Litaondolewa kabisa baada ya siku 90."
                )
            },
            status=status.HTTP_200_OK,
        )

    # ═══════════════════════════════════════════════════════════
    # RESTORE — rejesha tangazo lililofutwa (soft delete undo)
    # ═══════════════════════════════════════════════════════════
    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        """
        Rejesha tangazo lililofutwa (soft delete).

        Inaruhusu:
        - Seller kurejesha tangazo lake mwenyewe (kama ni soft-deleted).
        - Admin kurejesha tangazo lolote.

        Inarudisha tangazo lililorejeshwa.
        """
        # Tunatumia `all_objects` (SoftDeleteManager yenye
        # include_deleted=True) ili kupata listing iliyofutwa.
        listing = get_object_or_404(
            Listing.all_objects.select_related("seller", "category"),
            pk=pk,
        )

        # Ruhusa: seller mwenyewe au admin
        if not request.user.is_staff and listing.seller_id != request.user.id:
            return Response(
                {"detail": "Huna ruhusa ya kurejesha tangazo hili."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not listing.is_deleted:
            return Response(
                {"detail": "Tangazo hili halijafutwa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Restore — inarudisha `is_deleted=False`, `deleted_at=None`,
        # `deleted_by=None`, `deletion_reason=""`
        listing.restore()

        # Rudisha status ya listing kuwa AVAILABLE (hiari)
        # — inaweza kubadilishwa kulingana na mahitaji
        if listing.status == Listing.Status.ARCHIVED:
            listing.status = Listing.Status.AVAILABLE

        listing.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "detail": "Tangazo limerejeshwa.",
                "listing": ListingDetailSerializer(
                    listing, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )