# ============================================================
# apps/listings/views.py
# ============================================================

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, Q, F
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
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated

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

from .ownership import get_owned_or_public_listing

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
            Listing.Status.LIVE,
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
        if self.action in ["list", "retrieve", "similar"]:
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
        instance.refresh_from_db()
        data = ListingDetailSerializer(
            instance, context={"request": request},
        ).data

        fee = getattr(instance, "listing_fee", None)
        if fee is not None:
            data["payment"] = {
                "required": True,
                "amount": str(fee.amount),
                "amount_display": f"TZS {fee.amount:,.0f}",
                "currency": "TZS",
                "status": fee.payment_status,
                "listing_id": instance.id,
                "pay_endpoint": f"/api/listings/{instance.id}/fee/pay/",
            }
        else:
            data["payment"] = {
                "required": False,
                "amount": None,
                "amount_display": None,
                "currency": "TZS",
                "status": "NOT_CONFIGURED",
                "listing_id": instance.id,
                "pay_endpoint": f"/api/listings/{instance.id}/fee/pay/",
            }

        return Response(data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        listing = serializer.save(
            seller=self.request.user,
            status=Listing.Status.DRAFT,
        )

        # Auto-compute the fee right now so the seller sees the real
        # amount on the "Listing imeundwa" page. Every listing gets a
        # positive fee — create_listing_fee() auto-creates a rule if
        # none exists yet.
        try:
            from .services.listing_fee import create_listing_fee

            create_listing_fee(listing)
            listing.status = Listing.Status.PENDING_PAYMENT
            listing.save(update_fields=["status", "updated_at"])

        except Exception as exc:
            logger.exception(
                "Auto-fee computation failed for listing %s: %s",
                listing.pk, exc,
            )

    def perform_update(self, serializer):
        instance = self.get_object()

        if self.request.user.is_staff:
            serializer.save()
            return

        # Seller path — allow specific status transitions via PATCH,
        # but validate them so a seller cannot jump to arbitrary states.
        new_status = None
        if hasattr(self.request, "data") and isinstance(self.request.data, dict):
            new_status = self.request.data.get("status")

        if new_status and new_status != instance.status:
            allowed = {
                ("LIVE", "PAUSED"): True,
                ("PAUSED", "LIVE"): True,
                ("LIVE", "SOLD"): True,
                ("RESERVED", "SOLD"): True,
                ("PAUSED", "SOLD"): True,
            }
            if not allowed.get((instance.status, new_status)):
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    "status": (
                        f"Haiwezi kubadilika kutoka {instance.status} "
                        f"kwenda {new_status}."
                    )
                })

        serializer.save(seller=instance.seller)


    def retrieve(self, request, *args, **kwargs):
        """
        Ongeza views_count kila listing inapotazamwa.
        """
        instance = self.get_object()
        user = request.user

        should_count = True

        # Usihesabu kama ni seller mwenyewe au staff
        if user.is_authenticated and (
            user.id == instance.seller_id or user.is_staff
        ):
            should_count = False

        if should_count:
            Listing.objects.filter(pk=instance.pk).update(
                views_count=F("views_count") + 1
            )
            instance.refresh_from_db(fields=["views_count"])

        data = self.get_serializer(instance).data

        # Inject the same payment block so any listing detail page can
        # render the fee without a second call.
        fee = getattr(instance, "listing_fee", None)
        if fee is not None:
            data["payment"] = {
                "required": True,
                "amount": str(fee.amount),
                "amount_display": f"TZS {fee.amount:,.0f}",
                "currency": "TZS",
                "status": fee.payment_status,
                "listing_id": instance.id,
                "pay_endpoint": f"/api/listings/{instance.id}/fee/pay/",
            }
        elif getattr(instance, "status", "") in (
            "DRAFT", "PENDING_PAYMENT", "REJECTED",
        ):
            data["payment"] = {
                "required": False,
                "amount": None,
                "amount_display": None,
                "currency": "TZS",
                "status": "NOT_CONFIGURED",
                "listing_id": instance.id,
                "pay_endpoint": f"/api/listings/{instance.id}/fee/pay/",
            }
        else:
            data["payment"] = None

        return Response(data)

    @action(
        detail=True,
        methods=["get"],
        url_path="similar",
        permission_classes=[permissions.AllowAny],
    )
    def similar(self, request, pk=None):
        """
        Rudisha listings zinazofanana na listing hii.

        Mkakati wa hatua kwa hatua:
        1. Category + location + price (+/- 30%)
        2. Category + price (+/- 30%)
        3. Category pekee (relaxed zaidi)
        """
        listing = self.get_object()

        base = Listing.objects.filter(
            category=listing.category,
            status=Listing.Status.LIVE,
        ).exclude(
            pk=listing.pk,
        ).select_related(
            "seller", "category",
        ).prefetch_related(
            "images",
        )

        results = []

        # 1. Category + location + price
        qs = base
        if listing.location:
            location_keyword = listing.location.split(",")[0].strip()
            if location_keyword:
                qs = qs.filter(location__icontains=location_keyword)

        if listing.price:
            try:
                price = float(listing.price)
                qs = qs.filter(
                    price__gte=price * 0.7,
                    price__lte=price * 1.3,
                )
            except (TypeError, ValueError):
                pass

        results = list(qs.order_by("-is_featured", "-created_at")[:8])

        # 2. Ondoa location, jaribu price pekee
        if not results and listing.price:
            try:
                price = float(listing.price)
                qs2 = base.filter(
                    price__gte=price * 0.7,
                    price__lte=price * 1.3,
                )
                results = list(
                    qs2.order_by("-is_featured", "-created_at")[:8]
                )
            except (TypeError, ValueError):
                pass

        # 3. Category pekee
        if not results:
            results = list(
                base.order_by("-is_featured", "-created_at")[:8]
            )

        serializer = ListingListSerializer(
            results, many=True, context={"request": request},
        )
        return Response(serializer.data)

    # ═══════════════════════════════════════════════════════════════════
    # B-6: CHECK DUPLICATE
    # ═══════════════════════════════════════════════════════════════════
    @extend_schema(
        request=None,
        responses={200: None},
    )
    @action(
        detail=False, methods=["post"], url_path="check-duplicate",
        permission_classes=[permissions.IsAuthenticated],
    )
    def check_duplicate(self, request):
        """
        POST /api/listings/check-duplicate/
        Body: { title, price, location, category, window_days }
        Returns: { is_duplicate: bool, existing: {...} | null }
        """
        title = (request.data.get("title") or "").strip()
        location = (request.data.get("location") or "").strip()
        category = request.data.get("category") or request.data.get("category_id")
        try:
            window_days = int(request.data.get("window_days", 30))
        except (TypeError, ValueError):
            window_days = 30

        if not title:
            return Response(
                {"detail": "title inahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        since = timezone.now() - __import__("datetime").timedelta(days=window_days)
        qs = (
            Listing.objects
            .filter(
                seller=request.user,
                title__iexact=title,
                created_at__gte=since,
                is_deleted=False,
            )
        )
        if location:
            qs = qs.filter(location__icontains=location)
        if category:
            qs = qs.filter(category_id=category)

        existing = qs.order_by("-created_at").first()
        if not existing:
            return Response({"is_duplicate": False, "existing": None})

        return Response({
            "is_duplicate": True,
            "existing": {
                "id": existing.id,
                "title": existing.title,
                "status": existing.status,
                "price": str(existing.price),
                "location": existing.location,
                "created_at": existing.created_at,
            },
        })

    # ═══════════════════════════════════════════════════════════════════
    # B-7: PUBLISH (no-fee path)
    # ═══════════════════════════════════════════════════════════════════
        # ═══════════════════════════════════════════════════════════════════
    # B-7: PUBLISH
    # ═══════════════════════════════════════════════════════════════════
    @action(
        detail=True,
        methods=["post"],
        url_path="publish",
        permission_classes=[IsVerifiedUser, IsOwnerOrAdmin],
    )
    def publish(self, request, pk=None):
        """
        POST /api/listings/{id}/publish/
        Moves a DRAFT to PENDING_APPROVAL if no fee is required,
        otherwise to PENDING_PAYMENT.
        """
        from .services.listing_fee import create_listing_fee
        from .services.listing_moderation import _is_listing_fee_required_for

        listing = self.get_object()
        self.check_object_permissions(request, listing)

        if listing.status not in (
            Listing.Status.DRAFT,
            Listing.Status.REJECTED,
        ):
            return Response(
                {"detail": f"Tangazo halipo kwenye DRAFT. Hali: {listing.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fee already created at listing-create time. Check its status.
        fee = getattr(listing, "listing_fee", None)

        if fee is None:
            # Legacy listings — create on demand
            try:
                fee = create_listing_fee(listing)
            except Exception as exc:
                logger.exception(
                    "Could not create listing fee for %s: %s",
                    listing.pk, exc,
                )
                return Response(
                    {"detail": (
                        "Imeshindwa kuhesabu ada ya tangazo. "
                        "Wasiliana na msimamizi."
                    )},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        if fee.payment_status == ListingFee.PaymentStatus.PAID:
            # Already paid — move to PENDING_APPROVAL
            listing.status = Listing.Status.PENDING_APPROVAL
            listing.save(update_fields=["status", "updated_at"])
            return Response(
                ListingDetailSerializer(
                    listing, context={"request": request},
                ).data,
                status=status.HTTP_200_OK,
            )

        # Fee not paid — keep in PENDING_PAYMENT so the seller pays
        listing.status = Listing.Status.PENDING_PAYMENT
        listing.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "detail": "Malipo ya ada yanahitajika kabla ya kuwasilisha.",
                "payment_required": True,
                "fee_amount": str(fee.amount),
                "fee_currency": "TZS",
                "listing_id": listing.id,
                "status": listing.status,
            },
            status=status.HTTP_200_OK,
        )
    # ═══════════════════════════════════════════════════════════════════
    # B-8: DISAPPROVE (admin only)
    # ═══════════════════════════════════════════════════════════════════
    @extend_schema(
        request=ListingRejectionSerializer,
        responses={200: ListingDetailSerializer},
    )
    @action(
        detail=True, methods=["post"], url_path="disapprove",
        permission_classes=[permissions.IsAdminUser],
    )
    def disapprove(self, request, pk=None):
        """
        POST /api/listings/{id}/disapprove/
        Demote a live listing back to REJECTED (admin correction).
        """
        listing = self.get_object()

        if listing.status not in (
            Listing.Status.LIVE,
            Listing.Status.RESERVED,
            Listing.Status.PENDING_APPROVAL,
        ):
            return Response(
                {"detail": f"Tangazo halipo kwenye hali inayoweza kukataliwa. Hali: {listing.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ListingRejectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        listing.status = Listing.Status.REJECTED
        listing.rejected_by = request.user
        listing.rejected_at = timezone.now()
        listing.rejection_reason = serializer.validated_data["rejection_reason"]
        listing.approved_by = None
        listing.approved_at = None
        listing.save(update_fields=[
            "status", "rejected_by", "rejected_at", "rejection_reason",
            "approved_by", "approved_at", "updated_at",
        ])

        try:
            from apps.audit.services.audit import log_action
            log_action(
                request=request,
                action="listing.disapproved",
                target="Listing",
                target_id=listing.id,
                details=f"Disapproved: {listing.title}",
            )
        except Exception:
            pass

        return Response(
            ListingDetailSerializer(listing, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


    # ═══════════════════════════════════════════════════════════════════
    # PAUSE / UNPAUSE / MARK-SOLD
    # ═══════════════════════════════════════════════════════════════════
    @action(
        detail=True, methods=["post"], url_path="pause",
        permission_classes=[IsOwnerOrAdmin],
    )
    def pause(self, request, pk=None):
        """LIVE -> PAUSED. Seller hides the listing temporarily."""
        listing = self.get_object()
        self.check_object_permissions(request, listing)

        if listing.status != Listing.Status.LIVE:
            return Response(
                {"detail": f"Hali ya sasa ni {listing.status}, si LIVE."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        listing.status = Listing.Status.PAUSED
        listing.save(update_fields=["status", "updated_at"])
        return Response(
            ListingDetailSerializer(listing, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True, methods=["post"], url_path="unpause",
        permission_classes=[IsOwnerOrAdmin],
    )
    def unpause(self, request, pk=None):
        """PAUSED -> LIVE."""
        listing = self.get_object()
        self.check_object_permissions(request, listing)

        if listing.status != Listing.Status.PAUSED:
            return Response(
                {"detail": f"Hali ya sasa ni {listing.status}, si PAUSED."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        listing.status = Listing.Status.LIVE
        listing.save(update_fields=["status", "updated_at"])
        return Response(
            ListingDetailSerializer(listing, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True, methods=["post"], url_path="mark-sold",
        permission_classes=[IsOwnerOrAdmin],
    )
    def mark_sold(self, request, pk=None):
        """LIVE -> SOLD. Seller manually marks the listing as sold."""
        listing = self.get_object()
        self.check_object_permissions(request, listing)

        if listing.status not in (
            Listing.Status.LIVE,
            Listing.Status.RESERVED,
            Listing.Status.PAUSED,
        ):
            return Response(
                {"detail": (
                    f"Hali ya sasa ni {listing.status}. "
                    "Inaweza kuwa SOLD tu kutoka LIVE, RESERVED, au PAUSED."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        listing.status = Listing.Status.SOLD
        listing.save(update_fields=["status", "updated_at"])
        return Response(
            ListingDetailSerializer(listing, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    # ========================================================================
    # DESTROY - soft delete (default) au hard delete (admin)
    #   - Catch ProtectedError mwisho kama safety net, na
    #     tumia transaction.atomic() kuzuia partial deletes.
    # ========================================================================
    def destroy(self, request, *args, **kwargs):
        listing = self.get_object()

        is_hard = request.query_params.get(
            "hard", "false"
        ).lower() in ("true", "1", "yes")

        # Soft delete (default)
        if not (request.user.is_staff and is_hard):
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

        # ==================================================================
        # HARD DELETE
        # ==================================================================
        try:
            with transaction.atomic():
                # 1. ListingFee (PROTECT)
                ListingFee.objects.filter(listing=listing).delete()

                # 2. Leads (PROTECT) -- HARD DELETE
                # Lead ina Model.delete() override inayofanya
                # soft delete. Hata queryset.delete() inaheshimu
                # override hiyo. Kwa hivyo LAZIMA tutumie
                # hard_delete() kwa kila lead mmoja mmoja.
                try:
                    from apps.leads.models import Lead

                    lead_ids = list(
                        Lead._base_manager
                        .filter(listing=listing)
                        .values_list("pk", flat=True)
                    )

                    for lead_id in lead_ids:
                        lead = Lead._base_manager.get(pk=lead_id)
                        if hasattr(lead, "hard_delete"):
                            lead.hard_delete()
                        else:
                            Lead._base_manager.filter(pk=lead_id).delete()

                    remaining = Lead._base_manager.filter(
                        listing=listing
                    ).count()
                    if remaining:
                        raise RuntimeError(
                            f"Leads {remaining} zinarejelea tangazo "
                            f"hili bado."
                        )
                except ImportError:
                    logger.warning(
                        "[listings] leads app not available, skipping"
                    )

                # 3. Transaction chain
                # Mpangilio: InspectionPeriod -> Reservation ->
                # Transaction (kila moja ina PROTECT kwa iliyo juu).
                try:
                    from apps.transactions.models import (
                        Transaction,
                        Reservation,
                        InspectionPeriod,
                    )

                    tx_ids = list(
                        Transaction._base_manager
                        .filter(listing=listing)
                        .values_list("id", flat=True)
                    )

                    if tx_ids:
                        InspectionPeriod._base_manager.filter(
                            transaction_id__in=tx_ids,
                        ).delete()

                        Reservation._base_manager.filter(
                            transaction_id__in=tx_ids,
                        ).delete()

                        Transaction._base_manager.filter(
                            listing=listing,
                        ).delete()
                except ImportError:
                    logger.warning(
                        "[listings] transactions app not available, "
                        "skipping"
                    )

                # 4. DealRoom (PROTECT)
                try:
                    from apps.deals.models import DealRoom

                    DealRoom._base_manager.filter(
                        listing=listing,
                    ).delete()
                except ImportError:
                    logger.warning(
                        "[listings] deals app not available, skipping"
                    )

                # 5. Conversations + Messages
                # Msg.conversation ni PROTECT, hivyo LAZIMA
                # tufute messages kwanza, kisha conversations.
                try:
                    from apps.messaging.models import Conversation, Message

                    conv_ids = list(
                        Conversation._base_manager
                        .filter(listing=listing)
                        .values_list("id", flat=True)
                    )

                    if conv_ids:
                        for msg in Message._base_manager.filter(
                            conversation_id__in=conv_ids
                        ):
                            if hasattr(msg, "hard_delete"):
                                msg.hard_delete()
                            else:
                                Message._base_manager.filter(
                                    pk=msg.pk
                                ).delete()

                        for conv in Conversation._base_manager.filter(
                            id__in=conv_ids
                        ):
                            if hasattr(conv, "hard_delete"):
                                conv.hard_delete()
                            else:
                                Conversation._base_manager.filter(
                                    pk=conv.pk
                                ).delete()
                except ImportError:
                    logger.warning(
                        "[listings] messaging app not available, skipping"
                    )

                # 6. Related models zingine
                related_fields = [
                    "images",
                    "boosts",
                    "waiting_list_entries",
                    "saved_by",
                    "search_matches",
                    "banner_ads",
                    "leading_purchases",
                ]

                for field_name in related_fields:
                    manager = getattr(listing, field_name, None)
                    if manager is None:
                        continue
                    try:
                        for obj in manager.all():
                            if hasattr(obj, "hard_delete"):
                                obj.hard_delete()
                            else:
                                obj.delete()
                    except Exception as exc:
                        logger.warning(
                            "[listings] delete %s for listing %s "
                            "failed: %s",
                            field_name, listing.id, exc,
                        )
                        raise

                # 7. Details (one-to-one)
                detail_fields = [
                    "property_details",
                    "land_details",
                    "vehicle_details",
                    "business_details",
                    "equipment_details",
                ]
                for field_name in detail_fields:
                    try:
                        obj = getattr(listing, field_name)
                    except Exception:
                        obj = None
                    if obj is not None:
                        obj.delete()

                # 8. Hatimaye: hard delete listing
                listing.hard_delete()

        except ProtectedError as exc:
            protected = list(getattr(exc, "protected_objects", []))
            logger.error(
                "[listings] ProtectedError on hard_delete for %s: %s",
                listing.id, protected,
            )
            return Response(
                {
                    "detail": (
                        "Imeshindwa kufuta: kuna rekodi "
                        f"{len(protected)} zinazorejelea tangazo "
                        "hili."
                    ),
                    "protected_objects": [
                        str(o) for o in protected
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception(
                "[listings] hard_delete failed for %s: %s",
                listing.id, exc,
            )
            return Response(
                {"detail": f"Imeshindwa kufuta: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Tangazo limefutwa kabisa."},
            status=status.HTTP_204_NO_CONTENT,
        )


# ============================================================================
# REUSABLE CATEGORY DETAILS VIEWSET
# ============================================================================

class CategoryDetailsViewSet(viewsets.ModelViewSet):

    lookup_url_kwarg = "listing_id"

    detail_model = None
    detail_serializer = None
    required_category_slug = None
    already_exists_message = "Maelezo tayari yapo."
    created_message = "Maelezo yameongezwa."
    deleted_message = "Maelezo yamefutwa."

    queryset = PropertyDetails.objects.none()

    def get_serializer_class(self):
        return self.detail_serializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            if self.detail_model is not None:
                return self.detail_model.objects.none()
            return PropertyDetails.objects.none()

        listing = self.get_listing()
        return self.detail_model.objects.filter(listing=listing)

    def get_permissions(self):
        if self.action == "retrieve":
            return [permissions.AllowAny()]
        return [IsVerifiedUser(), IsOwnerOrAdmin()]

    def get_listing(self):
        return get_object_or_404(
            Listing.objects.select_related("seller", "category"),
            pk=self.kwargs[self.lookup_url_kwarg],
        )

    def check_owner(self, listing):
        if self.request.user.is_staff:
            return True
        return listing.seller_id == self.request.user.id

    def validate_listing_category(self, listing):
        if listing.category.slug != self.required_category_slug:
            return Response(
                {
                    "detail": (
                        f"Tangazo hili si la kundi "
                        f"{self.required_category_slug}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def create(self, request, *args, **kwargs):
        listing = self.get_listing()

        if not self.check_owner(listing):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kubadilisha "
                        "taarifa za tangazo ambalo si lako."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        category_error = self.validate_listing_category(listing)
        if category_error:
            return category_error

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                if self.detail_model.objects.filter(
                    listing=listing,
                ).exists():
                    raise IntegrityError("already_exists")
                serializer.save(listing=listing)
        except IntegrityError:
            return Response(
                {"detail": self.already_exists_message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        listing = self.get_listing()

        if not request.user.is_authenticated:
            if listing.status not in [
                Listing.Status.LIVE,
                Listing.Status.RESERVED,
                Listing.Status.SOLD,
            ]:
                return Response(
                    {"detail": "Tangazo halipatikani."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        elif not (
            request.user.is_staff
            or listing.seller_id == request.user.id
            or listing.status in [
                Listing.Status.LIVE,
                Listing.Status.RESERVED,
                Listing.Status.SOLD,
            ]
        ):
            return Response(
                {"detail": "Tangazo halipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        obj = get_object_or_404(self.detail_model, listing=listing)
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        return self._update_details(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update_details(request, partial=True)

    def _update_details(self, request, partial):
        listing = self.get_listing()

        if not self.check_owner(listing):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kubadilisha "
                        "taarifa za tangazo ambalo si lako."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        obj = get_object_or_404(self.detail_model, listing=listing)

        serializer = self.get_serializer(
            obj, data=request.data, partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        listing = self.get_listing()

        if not self.check_owner(listing):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kufuta taarifa hizi."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        obj = get_object_or_404(self.detail_model, listing=listing)
        obj.delete()

        return Response(
            {"detail": self.deleted_message},
            status=status.HTTP_200_OK,
        )

# ============================================================================
# PROPERTY
# ============================================================================

class PropertyDetailsViewSet(CategoryDetailsViewSet):
    detail_model = PropertyDetails
    detail_serializer = PropertyDetailsSerializer
    required_category_slug = CATEGORY_SLUGS["property"]
    queryset = PropertyDetails.objects.none()

    already_exists_message = (
        "Maelezo ya nyumba/jengo tayari yameongezwa kwenye tangazo hili."
    )
    deleted_message = "Maelezo ya nyumba/jengo yamefutwa."

# ============================================================================
# LAND
# ============================================================================

class LandDetailsViewSet(CategoryDetailsViewSet):
    detail_model = LandDetails
    detail_serializer = LandDetailsSerializer
    required_category_slug = CATEGORY_SLUGS["land"]
    queryset = LandDetails.objects.none()

    already_exists_message = (
        "Maelezo ya ardhi tayari yameongezwa kwenye tangazo hili."
    )
    deleted_message = "Maelezo ya ardhi yamefutwa."

# ============================================================================
# VEHICLE
# ============================================================================

class VehicleDetailsViewSet(CategoryDetailsViewSet):
    detail_model = VehicleDetails
    detail_serializer = VehicleDetailsSerializer
    required_category_slug = CATEGORY_SLUGS["vehicle"]
    queryset = VehicleDetails.objects.none()

    already_exists_message = (
        "Maelezo ya gari tayari yameongezwa kwenye tangazo hili."
    )
    deleted_message = "Maelezo ya gari yamefutwa."

# ============================================================================
# BUSINESS
# ============================================================================

class BusinessDetailsViewSet(CategoryDetailsViewSet):
    detail_model = BusinessDetails
    detail_serializer = BusinessDetailsSerializer
    required_category_slug = CATEGORY_SLUGS["business"]
    queryset = BusinessDetails.objects.none()

    already_exists_message = (
        "Maelezo ya biashara tayari yameongezwa kwenye tangazo hili."
    )
    deleted_message = "Maelezo ya biashara yamefutwa."

# ============================================================================
# EQUIPMENT
# ============================================================================

class EquipmentDetailsViewSet(CategoryDetailsViewSet):
    detail_model = EquipmentDetails
    detail_serializer = EquipmentDetailsSerializer
    required_category_slug = CATEGORY_SLUGS["equipment"]
    queryset = EquipmentDetails.objects.none()

    already_exists_message = (
        "Maelezo ya mashine tayari yameongezwa kwenye tangazo hili."
    )
    deleted_message = "Maelezo ya mashine yamefutwa."

# ============================================================================
# LISTING IMAGE VIEWSET
# ============================================================================

@extend_schema_view(
    list=extend_schema(
        summary="Orodha ya picha za tangazo",
        description="Huonyesha picha zote za tangazo kwa mpangilio.",
    ),
    retrieve=extend_schema(summary="Angalia picha ya tangazo"),
    create=extend_schema(
        summary="Ongeza picha kwenye tangazo",
        description=(
            "Muuzaji anaweza kuongeza picha kwenye tangazo lake. "
            "Admin anaweza kuongeza picha kwenye tangazo lolote."
        ),
        request={"multipart/form-data": ListingImageSerializer},
        responses={
            201: ListingImageSerializer,
            400: OpenApiResponse(description="Taarifa za picha si sahihi."),
            403: OpenApiResponse(description="Huna ruhusa ya kuongeza picha."),
        },
    ),
    partial_update=extend_schema(
        summary="Badilisha taarifa za picha",
        description="Badilisha picha kuwa primary au badilisha mpangilio wake.",
    ),
    destroy=extend_schema(summary="Futa picha ya tangazo"),
)
class ListingImageViewSet(viewsets.ModelViewSet):

    serializer_class = ListingImageSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    queryset = ListingImage.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ListingImage.objects.none()

        listing_id, err = require_int_listing_id(self.kwargs.get("listing_id"))
        if err:
            return ListingImage.objects.none()
        listing = get_object_or_404(Listing, pk=listing_id)
        user = self.request.user

        if user.is_authenticated and user.is_staff:
            return ListingImage.objects.filter(listing=listing).order_by(
                "ordering", "created_at",
            )

        if user.is_authenticated and listing.seller_id == user.id:
            return ListingImage.objects.filter(listing=listing).order_by(
                "ordering", "created_at",
            )

        if listing.status in [
            Listing.Status.LIVE,
            Listing.Status.RESERVED,
            Listing.Status.SOLD,
        ]:
            return ListingImage.objects.filter(listing=listing).order_by(
                "ordering", "created_at",
            )

        return ListingImage.objects.none()

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsVerifiedUser, IsOwnerOrAdmin]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        listing_id, err = require_int_listing_id(kwargs.get("listing_id"))
        if err:
            return err
        listing = get_object_or_404(Listing, pk=listing_id)

        if (
            not request.user.is_staff
            and listing.seller_id != request.user.id
        ):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kuongeza picha kwenye "
                        "tangazo ambalo si lako."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        image = request.FILES.get("image")
        if not image:
            return Response(
                {"detail": "Picha inahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        if image.content_type not in allowed_types:
            return Response(
                {
                    "detail": (
                        "Aina ya picha hairuhusiwi. "
                        "Tumia JPG, PNG au WEBP."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_size = 5 * 1024 * 1024
        if image.size > max_size:
            return Response(
                {"detail": "Picha haiwezi kuzidi ukubwa wa 5 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        is_primary = request.data.get("is_primary", False)
        if isinstance(is_primary, str):
            is_primary = is_primary.lower() in ["true", "1", "yes"]

        try:
            ordering = int(request.data.get("ordering", 0))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Ordering lazima iwe namba."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if ordering < 0:
            return Response(
                {"detail": "Ordering haiwezi kuwa chini ya sifuri."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            has_images = ListingImage.objects.filter(
                listing=listing,
            ).exists()

            if not has_images:
                is_primary = True

            if is_primary:
                ListingImage.objects.filter(
                    listing=listing, is_primary=True,
                ).update(is_primary=False)

            image_object = ListingImage.objects.create(
                listing=listing,
                image=image,
                is_primary=is_primary,
                ordering=ordering,
            )

        return Response(
            self.get_serializer(image_object).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        image_object = self.get_object()
        listing = image_object.listing

        if (
            not request.user.is_staff
            and listing.seller_id != request.user.id
        ):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kubadilisha picha ambalo si lako."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        is_primary = request.data.get("is_primary", None)
        ordering = request.data.get("ordering", None)

        if ordering is not None:
            try:
                ordering = int(ordering)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Ordering lazima iwe namba."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if ordering < 0:
                return Response(
                    {"detail": "Ordering haiwezi kuwa chini ya sifuri."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            if is_primary is not None:
                if isinstance(is_primary, str):
                    is_primary = is_primary.lower() in ["true", "1", "yes"]

                if is_primary:
                    ListingImage.objects.filter(
                        listing=listing, is_primary=True,
                    ).exclude(pk=image_object.pk).update(is_primary=False)
                    image_object.is_primary = True
                else:
                    if image_object.is_primary:
                        return Response(
                            {"detail": (
                                "Tangazo lazima liwe na angalau picha "
                                "moja kuu. Weka picha nyingine kuwa kuu "
                                "kwanza."
                            )},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

            if ordering is not None:
                image_object.ordering = ordering

            image_object.save()

        return Response(
            self.get_serializer(image_object).data,
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        image_object = self.get_object()
        listing = image_object.listing

        if (
            not request.user.is_staff
            and listing.seller_id != request.user.id
        ):
            return Response(
                {
                    "detail": (
                        "Huna ruhusa ya kufuta picha ambalo si lako."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        was_primary = image_object.is_primary

        with transaction.atomic():
            image_object.delete()

            if was_primary:
                next_image = (
                    ListingImage.objects
                    .filter(listing=listing)
                    .order_by("ordering", "created_at")
                    .first()
                )
                if next_image:
                    ListingImage.objects.filter(
                        listing=listing,
                    ).update(is_primary=False)
                    next_image.is_primary = True
                    next_image.save(update_fields=["is_primary"])

        return Response(
            {"detail": "Picha imefutwa."},
            status=status.HTTP_200_OK,
        )

# ============================================================================
# LISTING FEE API
# ============================================================================

@extend_schema(
    summary="Angalia ada ya tangazo",
    description=(
        "Hupata ada ya tangazo iliyotengenezwa. Kama haijatengenezwa, "
        "tumia endpoint ya payment ili kuitengeneza."
    ),
    responses={
        200: ListingFeeSerializer,
        403: OpenApiResponse(description="Huna ruhusa ya kuona ada hii."),
        404: OpenApiResponse(
            description="Tangazo au ada haijapatikana."
        ),
    },
)
class ListingFeeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, listing_id):
        listing_id, err = require_int_listing_id(listing_id)
        if err:
            return err
        listing = get_owned_or_public_listing(request.user, listing_id)
        if not listing:
            return Response(
                {
                    "detail": (
                        "Tangazo halipatikani. Kama ni lako, "
                        "fungua Mali Zangu na ujaribu tena."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if (
            not request.user.is_staff
            and listing.seller_id != request.user.id
        ):
            return Response(
                {"detail": "Huna ruhusa ya kuona ada ya tangazo hili."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            listing_fee = ListingFee.objects.get(listing=listing)
        except ListingFee.DoesNotExist:
            # Auto-create the fee from the rule so the frontend always
            # gets a real amount instead of "TZS 0 / not configured".
            try:
                from .services.listing_fee import create_listing_fee
                listing_fee = create_listing_fee(listing)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).exception(
                    "Could not compute fee for listing %s: %s",
                    listing.pk, exc,
                )
                return Response(
                    {
                        "detail": (
                            "Imeshindwa kuhesabu ada ya tangazo. "
                            "Wasiliana na msimamizi."
                        )
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            ListingFeeSerializer(
                listing_fee, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

# ============================================================================
# LISTING FEE PAYMENT API
# ============================================================================

@extend_schema(
    summary="Lipa ada ya tangazo",
    description=(
        "Huthibitisha malipo ya ada ya tangazo. "
        "Inaunga mkono FimiPay au credits za bundle."
    ),
    request=ListingFeePaymentSerializer,
    responses={
        200: ListingFeeSerializer,
        400: OpenApiResponse(description="Malipo hayawezi kukamilishwa."),
        403: OpenApiResponse(description="Huna ruhusa ya kulipia tangazo hili."),
        404: OpenApiResponse(description="Tangazo au ada haijapatikana."),
    },
)
class ListingFeePaymentView(APIView):
    """
    POST /api/listings/{id}/fee/pay/

    Three paths, decided by the request body:

    1. Free category (fee == 0):
       Body: { "payment_reference": "free" }
       → Fee marked PAID, listing → PENDING_APPROVAL

    2. Bundle credits:
       Body: { "payment_reference": "credits" }
       → Credit consumed, fee PAID, listing → PENDING_APPROVAL

    3. FimiPay (mobile money / card / bank):
       Body: { "payment_method": "mpesa", "phone": "255..." }
       → Returns { fimipay: { order_id, payment_status: "PENDING" } }
       → Webhook flips status when the payment lands.

    Permission: seller-only.
    Allowed listing states: DRAFT, PENDING_PAYMENT, REJECTED (retry).
    """
    permission_classes = [permissions.IsAuthenticated]

    # ------------------------------------------------------------------
    def post(self, request, listing_id):
        listing_id, err = require_int_listing_id(listing_id)
        if err:
            return err
        listing = get_owned_or_public_listing(request.user, listing_id)
        if not listing:
            return Response(
                {
                    "detail": (
                        "Tangazo halipatikani. Kama ni lako, "
                        "fungua Mali Zangu na ujaribu tena."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if not request.user.is_staff and listing.seller_id != request.user.id:
            return Response(
                {"detail": "Huna ruhusa ya kulipia ada ya tangazo hili."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Paid already?
        existing_fee = getattr(listing, "listing_fee", None)
        if (
            existing_fee is not None
            and existing_fee.payment_status == ListingFee.PaymentStatus.PAID
        ):
            return Response(
                {
                    "detail": "Ada ya tangazo hili tayari imelipwa.",
                    "listing": {
                        "id": listing.id,
                        "status": listing.status,
                    },
                    "fee": {
                        "amount": str(existing_fee.amount),
                        "payment_status": existing_fee.payment_status,
                    },
                },
                status=status.HTTP_200_OK,
            )

        # Ensure a fee row exists (auto-compute if legacy)
        if existing_fee is None:
            try:
                from .services.listing_fee import create_listing_fee
                existing_fee = create_listing_fee(listing)
            except Exception as exc:
                logger.exception(
                    "Could not create fee for listing %s: %s",
                    listing.id, exc,
                )
                return Response(
                    {"detail": (
                        "Ada ya tangazo haijatengenezwa. "
                        "Wasiliana na msimamizi."
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        payment_reference = (
            request.data.get("payment_reference") or ""
        ).strip().lower()

        # ============================================================
        # PATH 1 — FREE
        # ============================================================
        if payment_reference == "free":
            if existing_fee.amount > 0:
                # Seller is trying to skip a real fee — reject.
                return Response(
                    {"detail": (
                        "Ada ya tangazo hili si sifuri. "
                        "Tafadhali lipia kiasi halisi."
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            from django.db import transaction as db_tx
            with db_tx.atomic():
                existing_fee.payment_status = ListingFee.PaymentStatus.PAID
                existing_fee.payment_reference = f"free-{listing.id}"
                existing_fee.paid_at = timezone.now()
                existing_fee.save(update_fields=[
                    "payment_status", "payment_reference", "paid_at",
                    "updated_at",
                ])

                listing.status = Listing.Status.PENDING_APPROVAL
                listing.save(update_fields=["status", "updated_at"])

            # Notify admin
            try:
                from apps.notifications.models import Notification
                from apps.notifications.services.notification import (
                    create_notification_for_admins,
                )
                create_notification_for_admins(
                    notification_type=Notification.NotificationType.LISTING_CREATED,
                    title="Listing tayari kwa idhini (bure)",
                    message=f'"{listing.title}" imewasilishwa bila ada.',
                    related_object_type="listings.Listing",
                    related_object_id=listing.id,
                    action_url=f"/smk-control-9x7k/moderation",
                )
            except Exception:
                logger.exception("admin notification for free listing failed")

            return Response(
                {
                    "message": "Tangazo limewasilishwa kwa admin.",
                    "listing": {"id": listing.id, "status": listing.status},
                    "via": "free",
                },
                status=status.HTTP_200_OK,
            )

        # ============================================================
        # PATH 2 — CREDITS
        # ============================================================
        if payment_reference == "credits":
            import uuid as _uuid
            from django.db import transaction as db_tx
            from apps.credits.services import consume_credit

            with db_tx.atomic():
                if not consume_credit(user=request.user, service_key="listing"):
                    return Response(
                        {"detail": "Hakuna listing credits za kutosha."},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )

                ref = f"credits-{existing_fee.pk}-{_uuid.uuid4().hex[:12]}"
                existing_fee.payment_status = ListingFee.PaymentStatus.PAID
                existing_fee.payment_reference = ref
                existing_fee.paid_at = timezone.now()
                existing_fee.save(update_fields=[
                    "payment_status", "payment_reference", "paid_at",
                    "updated_at",
                ])

                listing.status = Listing.Status.PENDING_APPROVAL
                listing.save(update_fields=["status", "updated_at"])

            # Notify admin
            try:
                from apps.notifications.models import Notification
                from apps.notifications.services.notification import (
                    create_notification_for_admins,
                )
                create_notification_for_admins(
                    notification_type=Notification.NotificationType.LISTING_CREATED,
                    title="Listing tayari kwa idhini (credits)",
                    message=f'"{listing.title}" imewasilishwa kwa credits.',
                    related_object_type="listings.Listing",
                    related_object_id=listing.id,
                    action_url=f"/smk-control-9x7k/moderation",
                )
            except Exception:
                logger.exception("admin notification for credits listing failed")

            return Response(
                {
                    "message": "Malipo yamekamilika kwa credits.",
                    "listing": {"id": listing.id, "status": listing.status},
                    "via": "credits",
                },
                status=status.HTTP_200_OK,
            )

        # ============================================================
        # PATH 3 — FIMIPAY (default)
        # ============================================================
        try:
            from .services.listing_payment import initiate_listing_fee_payment
            data = initiate_listing_fee_payment(
                listing=listing,
                user=request.user,
                payment_method=request.data.get("payment_method", "mobile"),
                phone=request.data.get("phone", ""),
            )
        except DjangoValidationError as exc:
            return Response(
                {"detail": getattr(exc, "messages", [str(exc)])},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ValidationError as exc:
            return Response(
                exc.detail if isinstance(exc.detail, dict)
                else {"detail": exc.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Malipo yameanzishwa. Angalia simu yako kuidhinisha.",
                "fimipay": data,
            },
            status=status.HTTP_201_CREATED,
        )


class AdminPendingListingsView(GenericAPIView):
    """
    GET /api/listings/admin/pending/

    Returns ONLY listings that are PENDING_APPROVAL *and* have their
    listing fee PAID. Listings in DRAFT or PENDING_PAYMENT are
    intentionally hidden from admins — they belong to the seller
    until payment is confirmed.
    """
    permission_classes = [permissions.IsAdminUser]
    serializer_class = AdminPendingListingSerializer

    def get(self, request):
        listings = (
            Listing.objects
            .filter(
                status=Listing.Status.PENDING_APPROVAL,
                listing_fee__payment_status="PAID",
            )
            .select_related("seller", "category", "listing_fee")
            .prefetch_related("images")
            .order_by("-created_at")
        )

        page = self.paginate_queryset(listings)
        serializer = AdminPendingListingSerializer(
            page if page is not None else listings,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)

        return Response(
            {"count": listings.count(), "results": serializer.data},
            status=status.HTTP_200_OK,
        )

# ============================================================================
# ADMIN APPROVE LISTING
# ============================================================================

@extend_schema(
    summary="Idhinisha tangazo",
    description=(
        "Humruhusu admin kuidhinisha tangazo lililo kwenye "
        "PENDING_APPROVAL. Ada ya tangazo lazima iwe imelipwa "
        "kabla ya tangazo kuidhinishwa."
    ),
    responses={
        200: ListingDetailSerializer,
        400: OpenApiResponse(description="Tangazo haliwezi kuidhinishwa."),
        403: OpenApiResponse(description="Ni admin pekee."),
        404: OpenApiResponse(description="Tangazo halijapatikana."),
    },
)
class AdminApproveListingView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, listing_id):
        try:
            listing = approve_listing(
                listing_id=listing_id,
                admin_user=request.user,
            )
        except Listing.DoesNotExist:
            return Response(
                {"detail": "Tangazo halijapatikana."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as exc:
            detail = getattr(exc, "detail", str(exc))
            return Response(
                {"detail": detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from apps.audit.services.audit import log_action
            log_action(
                request=request,
                action="listing.approved",
                target="Listing",
                target_id=listing.id,
                details=f"Approved: {listing.title}",
            )
        except Exception:
            pass

        serializer = ListingDetailSerializer(
            listing, context={"request": request},
        )

        return Response(
            {
                "detail": "Tangazo limeidhinishwa na sasa linapatikana.",
                "listing": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

# ============================================================================
# ADMIN REJECT LISTING
# ============================================================================

@extend_schema(
    summary="Kataa tangazo",
    description=(
        "Humruhusu admin kukataa tangazo lililo kwenye "
        "PENDING_APPROVAL. Sababu ya kukataa inahitajika."
    ),
    request=ListingRejectionSerializer,
    responses={
        200: ListingDetailSerializer,
        400: OpenApiResponse(description="Sababu haijawekwa."),
        403: OpenApiResponse(description="Ni admin pekee."),
        404: OpenApiResponse(description="Tangazo halijapatikana."),
    },
)
class AdminRejectListingView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, listing_id):
        serializer = ListingRejectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            listing = reject_listing(
                listing_id=listing_id,
                admin_user=request.user,
                rejection_reason=serializer.validated_data[
                    "rejection_reason"
                ],
            )
        except Listing.DoesNotExist:
            return Response(
                {"detail": "Tangazo halijapatikana."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as exc:
            detail = getattr(exc, "detail", str(exc))
            return Response(
                {"detail": detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from apps.audit.services.audit import log_action
            log_action(
                request=request,
                action="listing.rejected",
                target="Listing",
                target_id=listing.id,
                details=f"Rejected: {listing.title} | Reason: {serializer.validated_data.get('rejection_reason', '')}",
            )
        except Exception:
            pass

        response_serializer = ListingDetailSerializer(
            listing, context={"request": request},
        )

        return Response(
            {
                "detail": "Tangazo limekataliwa.",
                "listing": response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    

# ============================================================================
# CHECK DUPLICATE LISTING
# ============================================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def check_duplicate_listing(request):
    """
    Angalia kama mtumiaji ana listing inayofanana.
    Inatumika kuzuia kuweka listing mara mbili.
    """
    user = request.user
    title = (request.data.get("title") or "").strip()
    price = request.data.get("price")
    location = (request.data.get("location") or "").strip()

    if not title:
        return Response(
            {"detail": "title inahitajika."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qs = Listing.objects.filter(
        seller=user,
        title__iexact=title,
    )

    if price is not None:
        try:
            price_val = float(price)
            if price_val > 0:
                qs = qs.filter(price=price_val)
        except (TypeError, ValueError):
            pass

    if location:
        qs = qs.filter(location__icontains=location)

    existing = qs.first()

    return Response(
        {
            "is_duplicate": existing is not None,
            "existing": (
                {
                    "id": existing.id,
                    "title": existing.title,
                    "price": str(existing.price),
                    "location": existing.location,
                    "status": existing.status,
                }
                if existing
                else None
            ),
        },
        status=status.HTTP_200_OK,
    )


# ============================================================================
# PUBLISH LISTING — wasilisha kwa admin approval
# ============================================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def publish_listing(request, pk):
    """
    Submit listing kwa admin approval.
    Kila listing (free au paid) inaenda PENDING_APPROVAL.
    """
    try:
        listing = Listing.objects.get(pk=pk)
    except Listing.DoesNotExist:
        return Response(
            {"detail": "Tangazo halijapatikana."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not request.user.is_staff and listing.seller_id != request.user.id:
        return Response(
            {"detail": "Huna ruhusa ya kuchapisha tangazo hili."},
            status=status.HTTP_403_FORBIDDEN,
        )

    listing.status = Listing.Status.PENDING_APPROVAL
    listing.save(update_fields=["status", "updated_at"])

    return Response(
        {
            "detail": (
                "Tangazo limewasilishwa kwa admin. "
                "Litaonekana baada ya kuidhinishwa."
            ),
            "listing_id": listing.id,
            "status": listing.status,
        },
        status=status.HTTP_200_OK,
    )

# ============================================================================
# ADMIN — ABANDONED DRAFTS
# ============================================================================

class AdminDraftListingsView(GenericAPIView):
    """
    GET /api/listings/admin/drafts/?older_than_hours=24

    Returns listings stuck in DRAFT or PENDING_PAYMENT for longer than
    the given threshold. Useful for outreach and spotting bugs.
    """
    permission_classes = [permissions.IsAdminUser]
    serializer_class = AdminPendingListingSerializer

    def get(self, request):
        try:
            hours = int(request.query_params.get("older_than_hours", 24))
        except (TypeError, ValueError):
            hours = 24
        cutoff = timezone.now() - __import__("datetime").timedelta(hours=hours)

        listings = (
            Listing.objects
            .filter(
                status__in=[
                    Listing.Status.DRAFT,
                    Listing.Status.PENDING_PAYMENT,
                ],
                updated_at__lt=cutoff,
            )
            .select_related("seller", "category")
            .prefetch_related("images")
            .order_by("updated_at")
        )

        page = self.paginate_queryset(listings)
        serializer = AdminPendingListingSerializer(
            page if page is not None else listings,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response({"count": listings.count(), "results": serializer.data})


# ============================================================================
# ADMIN — BULK MODERATION
# ============================================================================

class AdminBulkApproveView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        ids = request.data.get("ids") or []
        succeeded, failed = [], []
        for pk in ids:
            try:
                approve_listing(listing_id=pk, admin_user=request.user)
                succeeded.append(pk)
            except Exception as exc:
                failed.append({"id": pk, "error": str(exc)})
        try:
            from apps.audit.services.audit import log_action
            log_action(
                request=request,
                action="listing.bulk_approved",
                target="Listing",
                target_id=None,
                details=f"Bulk approved {len(succeeded)}: ids={succeeded[:20]}",
            )
        except Exception:
            pass
        return Response({"succeeded": succeeded, "failed": failed})


class AdminBulkRejectView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        ids = request.data.get("ids") or []
        reason = (request.data.get("reason") or "").strip() or "Bulk rejection"
        succeeded, failed = [], []
        for pk in ids:
            try:
                reject_listing(
                    listing_id=pk,
                    admin_user=request.user,
                    rejection_reason=reason,
                )
                succeeded.append(pk)
            except Exception as exc:
                failed.append({"id": pk, "error": str(exc)})
        try:
            from apps.audit.services.audit import log_action
            log_action(
                request=request,
                action="listing.bulk_rejected",
                target="Listing",
                target_id=None,
                details=f"Bulk rejected {len(succeeded)}: ids={succeeded[:20]}",
            )
        except Exception:
            pass
        return Response({"succeeded": succeeded, "failed": failed})


class AdminBulkDeleteView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        ids = request.data.get("ids") or []
        reason = (request.data.get("reason") or "").strip() or "Bulk delete"
        succeeded, failed = [], []
        for pk in ids:
            listing = Listing.objects.filter(pk=pk).first()
            if not listing:
                failed.append({"id": pk, "error": "Not found"})
                continue
            try:
                listing.delete(by=request.user, reason=reason)
                succeeded.append(pk)
            except Exception as exc:
                failed.append({"id": pk, "error": str(exc)})
        try:
            from apps.audit.services.audit import log_action
            log_action(
                request=request,
                action="listing.bulk_deleted",
                target="Listing",
                target_id=None,
                details=f"Bulk deleted {len(succeeded)}: ids={succeeded[:20]}",
            )
        except Exception:
            pass
        return Response({"succeeded": succeeded, "failed": failed})


# ============================================================================
# SELLER — UNPAID LISTINGS (dashboard widget)
# ============================================================================

class MyUnpaidListingsView(GenericAPIView):
    """
    GET /api/listings/mine/unpaid/

    Returns the seller's own listings that are waiting for payment,
    so the frontend can show a "you have 3 unpaid listings" banner.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ListingListSerializer

    def get(self, request):
        listings = (
            Listing.objects
            .filter(
                seller=request.user,
                status__in=[
                    Listing.Status.DRAFT,
                    Listing.Status.PENDING_PAYMENT,
                ],
            )
            .select_related("seller", "category", "listing_fee")
            .prefetch_related("images")
            .order_by("-created_at")
        )

        page = self.paginate_queryset(listings)
        serializer = ListingListSerializer(
            page if page is not None else listings,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)

        return Response({
            "count": listings.count(),
            "results": serializer.data,
        })
