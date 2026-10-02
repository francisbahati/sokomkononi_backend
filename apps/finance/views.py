from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.boosting.models import ListingBoost
from apps.listings.models import ListingFee
from apps.transactions.models import Reservation

from .serializers import (
    FinancialDashboardSerializer,
    MyTransactionSerializer,
    RevenueRecordSerializer,
)
from .services.revenue import (
    calculate_financial_dashboard,
    get_revenue_records,
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class FinancialDashboardView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="period", type=str, required=False,
                enum=["all", "today", "week", "month"],
            ),
        ],
        responses=FinancialDashboardSerializer,
    )
    def get(self, request):
        period = request.query_params.get("period", "all")

        if period not in {"all", "today", "week", "month"}:
            return Response(
                {"detail": "Invalid period."}, status=400,
            )

        data = calculate_financial_dashboard(period)
        return Response(FinancialDashboardSerializer(data).data)


class RevenueReportView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="period", type=str, required=False,
                enum=["all", "today", "week", "month"],
            ),
            OpenApiParameter(
                name="source", type=str, required=False,
                enum=["all", "listing_fee", "reservation", "boosting", "advertisement", "bundle", "refund"],
            ),
        ],
        responses=RevenueRecordSerializer(many=True),
    )
    def get(self, request):
        period = request.query_params.get("period", "all")
        source = request.query_params.get("source", "all")

        if period not in {"all", "today", "week", "month"}:
            return Response({"detail": "Invalid period."}, status=400)

        if source not in {
            "all", "listing_fee", "reservation", "boosting",
            "advertisement", "bundle", "refund",
        }:
            return Response({"detail": "Invalid source."}, status=400)

        records = get_revenue_records(period=period, source=source)

        # Cap the response — paginate further if needed.
        try:
            limit = min(int(request.query_params.get("limit", 500)), 2000)
        except ValueError:
            limit = 500
        truncated = len(records) > limit
        records = records[:limit]

        serializer = RevenueRecordSerializer(records, many=True)

        return Response({
            "period": period,
            "source": source,
            "count": len(records),
            "truncated": truncated,
            "results": serializer.data,
        })


class MyTransactionsPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class MyTransactionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses=MyTransactionSerializer(many=True),
    )
    def get(self, request):
        user = request.user
        records = []

        # ══════════════════════════════════════════════════════════
        # 1. LISTING FEES
        # ══════════════════════════════════════════════════════════
        for item in ListingFee.objects.filter(
            seller=user,
        ).select_related("listing").order_by("-created_at"):
            records.append({
                "id": f"lf_{item.pk}",
                "source": "listing_fee",
                "ref": item.payment_reference or f"LF-{item.pk}",
                "type": "listing_fee",
                "title": f"Listing Fee — {item.listing.title}",
                "listing_id": item.listing_id,
                "listing_title": item.listing.title,
                "amount": item.amount,
                "status": self._map_status(item.payment_status),
                "payment_status": item.payment_status,
                "payment_reference": item.payment_reference,
                "method": None,
                "paid_at": item.paid_at,
                "created_at": item.created_at,
            })

        # ══════════════════════════════════════════════════════════
        # 2. BOOSTS
        # ══════════════════════════════════════════════════════════
        for item in ListingBoost.objects.filter(
            seller=user,
        ).select_related("listing", "package").order_by("-created_at"):
            records.append({
                "id": f"b_{item.pk}",
                "source": "boosting",
                "ref": item.payment_reference or f"B-{item.pk}",
                "type": "boost",
                "title": f"Boost — {item.listing.title}",
                "listing_id": item.listing_id,
                "listing_title": item.listing.title,
                "amount": item.amount,
                "status": self._map_status(item.payment_status),
                "payment_status": item.payment_status,
                "payment_reference": item.payment_reference,
                "method": None,
                "paid_at": item.paid_at,
                "created_at": item.created_at,
            })

        # ══════════════════════════════════════════════════════════
        # 3. RESERVATIONS
        # ══════════════════════════════════════════════════════════
        for item in Reservation.objects.filter(
            transaction__buyer=user,
        ).select_related(
            "transaction", "transaction__listing",
        ).order_by("-created_at"):
            listing = item.transaction.listing
            records.append({
                "id": f"r_{item.pk}",
                "source": "reservation",
                "ref": item.payment_reference or f"R-{item.pk}",
                "type": "reservation",
                "title": f"Reservation — {listing.title}",
                "listing_id": listing.pk,
                "listing_title": listing.title,
                "amount": item.deposit_amount,
                "status": self._map_status(item.payment_status),
                "payment_status": item.payment_status,
                "payment_reference": item.payment_reference,
                "method": None,
                "paid_at": item.paid_at,
                "created_at": item.created_at,
            })

        # ══════════════════════════════════════════════════════════
        # 4. BUNDLE PURCHASES — MPYA
        # ══════════════════════════════════════════════════════════
        from apps.bundles.models import BundlePurchase

        for item in BundlePurchase.objects.filter(
            user=user,
            status=BundlePurchase.Status.PAID,
        ).select_related("bundle").order_by("-created_at"):
            credits = item.credits_snapshot or {}
            credits_list = (
                ", ".join(
                    f"{v}× {k}"
                    for k, v in credits.items()
                    if float(v) > 0
                )
                if isinstance(credits, dict)
                else ""
            )
            bundle_name = (
                item.bundle.name_sw
                if item.bundle and hasattr(item.bundle, "name_sw")
                else "Bundle"
            )
            title = (
                f"Bundle — {credits_list}"
                if credits_list
                else f"Bundle — {bundle_name}"
            )

            records.append({
                "id": f"bp_{item.pk}",
                "source": "bundle_purchase",
                "ref": item.payment_reference or f"BP-{item.pk}",
                "type": "bundle_purchase",
                "title": title,
                "amount": item.amount,
                "status": "COMPLETED",
                "payment_status": "PAID",
                "payment_reference": item.payment_reference,
                "method": None,
                "paid_at": item.paid_at,
                "created_at": item.created_at,
                "bundle_id": item.bundle_id,
                "bundle_name": bundle_name,
                "credits": credits,
            })

        # ══════════════════════════════════════════════════════════
        # SORT + PAGINATE
        # ══════════════════════════════════════════════════════════
        records.sort(key=lambda r: r["created_at"], reverse=True)

        paginator = MyTransactionsPagination()
        page = paginator.paginate_queryset(records, request)

        serializer = MyTransactionSerializer(
            page if page is not None else records, many=True,
        )

        if page is not None:
            return paginator.get_paginated_response(serializer.data)

        return Response({
            "count": len(records),
            "results": serializer.data,
        })

    @staticmethod
    def _map_status(payment_status):
        mapping = {
            "PAID": "COMPLETED",
            "PENDING": "PENDING",
            "FAILED": "FAILED",
            "REFUNDED": "REFUNDED",
        }
        return mapping.get(payment_status, "PENDING")


# ============================================================
# REVENUE — SUCCESS FEE CONFIG VIEW (Singleton)
# ============================================================

from rest_framework import status, viewsets
from rest_framework.decorators import action

from .models import SuccessFeeConfig, SystemFeatureToggle
from .serializers import (
    SuccessFeeConfigSerializer,
    SystemFeatureToggleSerializer,
)


class SuccessFeeConfigView(APIView):
    """
    Singleton viewset — SuccessFeeConfig moja (pk=1).

    GET   /api/finance/success-fee-config/
    PATCH /api/finance/success-fee-config/
    POST  /api/finance/success-fee-config/toggle/
    """
    permission_classes = [IsAdminUser]

    def get_object(self):
        obj, _ = SuccessFeeConfig.objects.get_or_create(
            key="default",
            defaults={
                "label_sw": "Ada ya Mafanikio",
                "label_en": "Success Fee",
                "desc_sw": "Ada ndogo ya kupakua ripoti ya miamala.",
                "desc_en": "Small fee to download transactions report.",
                "percentage": 2.0,
                "min_fee": 5000,
                "max_fee": 500000,
                "is_enabled": True,
            },
        )
        return obj

    def get(self, request):
        return Response(SuccessFeeConfigSerializer(self.get_object()).data)

    def patch(self, request):
        obj = self.get_object()
        serializer = SuccessFeeConfigSerializer(
            obj, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def post(self, request):
        if request.path.endswith("/toggle/"):
            obj = self.get_object()
            obj.is_enabled = not obj.is_enabled
            obj.save(update_fields=["is_enabled", "updated_at"])
            return Response({
                "key": obj.key,
                "is_enabled": obj.is_enabled,
            })
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


# ============================================================
# REVENUE — SYSTEM FEATURE TOGGLE VIEWSET
# ============================================================

class SystemFeatureToggleViewSet(viewsets.ModelViewSet):
    """
    Toggles za jumla.

    GET    /api/finance/toggles/                      list
    GET    /api/finance/toggles/{key}/                retrieve
    PATCH  /api/finance/toggles/{key}/                partial update
    POST   /api/finance/toggles/{key}/toggle/         toggle
    POST   /api/finance/toggles/bulk-toggle/          bulk toggle
    """
    queryset = SystemFeatureToggle.objects.all()
    serializer_class = SystemFeatureToggleSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "key"
    http_method_names = ["get", "patch", "post"]

    @action(detail=True, methods=["post"])
    def toggle(self, request, key=None):
        toggle = self.get_object()
        toggle.is_enabled = not toggle.is_enabled
        toggle.save(update_fields=["is_enabled", "updated_at"])
        return Response({
            "key": toggle.key,
            "is_enabled": toggle.is_enabled,
        })

    @action(detail=False, methods=["post"], url_path="bulk-toggle")
    def bulk_toggle(self, request):
        """
        POST /api/finance/toggles/bulk-toggle/
        Body: { listing_fee: true, boost_fee: false, ... }
        """
        updates = request.data
        updated = []
        for key, value in updates.items():
            try:
                toggle = SystemFeatureToggle.objects.get(key=key)
                toggle.is_enabled = bool(value)
                toggle.save(update_fields=["is_enabled", "updated_at"])
                updated.append({
                    "key": key,
                    "is_enabled": toggle.is_enabled,
                })
            except SystemFeatureToggle.DoesNotExist:
                pass
        return Response({"updated": updated})


# ============================================================
# REVENUE — OVERVIEW (Bulk)
# ============================================================

class RevenueOverviewView(APIView):
    """
    GET /api/finance/revenue-overview/
    Returns everything in one go.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.listings.models import ListingFeeRule
        from apps.listings.serializers_fee_rules import ListingFeeRuleSerializer
        from apps.boosting.models import BoostPackage
        from apps.boosting.serializers import BoostPackageSerializer
        from apps.reservation_rates.models import ReservationRate
        from apps.reservation_rates.serializers import ReservationRateSerializer
        from apps.advertisement_fees.models import AdvertisementFeeConfig
        from apps.advertisement_fees.serializers import (
            AdvertisementFeeConfigSerializer,
        )
        from apps.leading_fees.models import LeadingFeeConfig
        from apps.leading_fees.serializers import LeadingFeeConfigSerializer

        return Response({
            "listing_fees": ListingFeeRuleSerializer(
                ListingFeeRule.objects.filter(is_deleted=False),
                many=True,
            ).data,
            "reservation_rate": ReservationRateSerializer(
                ReservationRate.objects.first(),
            ).data if ReservationRate.objects.exists() else None,
            "boost_packages": BoostPackageSerializer(
                BoostPackage.objects.filter(is_deleted=False).order_by("ordering"),
                many=True,
            ).data,
            "advertisement_fee": AdvertisementFeeConfigSerializer(
                AdvertisementFeeConfig.objects.first(),
            ).data if AdvertisementFeeConfig.objects.exists() else None,
            "leading_fee": LeadingFeeConfigSerializer(
                LeadingFeeConfig.objects.first(),
            ).data if LeadingFeeConfig.objects.exists() else None,
            "success_fee": SuccessFeeConfigSerializer(
                SuccessFeeConfig.objects.get_or_create(key="default")[0],
            ).data,
            "system_toggles": SystemFeatureToggleSerializer(
                SystemFeatureToggle.objects.all(),
                many=True,
            ).data,
        })