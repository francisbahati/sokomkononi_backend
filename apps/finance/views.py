from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions
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
    """
    Only Django staff/admin users can access system-wide financial data.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class FinancialDashboardView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Financial dashboard",
        parameters=[
            OpenApiParameter(
                name="period",
                type=str,
                required=False,
                enum=["all", "today", "week", "month"],
            ),
        ],
        responses=FinancialDashboardSerializer,
    )
    def get(self, request):
        period = request.query_params.get("period", "all")

        if period not in {"all", "today", "week", "month"}:
            return Response(
                {
                    "detail": (
                        "Invalid period. "
                        "Use all, today, week, or month."
                    )
                },
                status=400,
            )

        data = calculate_financial_dashboard(period)
        serializer = FinancialDashboardSerializer(data)

        return Response(serializer.data)


class RevenueReportView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Detailed revenue report",
        parameters=[
            OpenApiParameter(
                name="period",
                type=str,
                required=False,
                enum=["all", "today", "week", "month"],
            ),
            OpenApiParameter(
                name="source",
                type=str,
                required=False,
                enum=[
                    "all",
                    "listing_fee",
                    "reservation",
                    "boosting",
                    "refund",
                ],
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
            "all",
            "listing_fee",
            "reservation",
            "boosting",
            "refund",
        }:
            return Response({"detail": "Invalid source."}, status=400)

        records = get_revenue_records(period=period, source=source)
        serializer = RevenueRecordSerializer(records, many=True)

        return Response(
            {
                "period": period,
                "source": source,
                "count": len(records),
                "results": serializer.data,
            }
        )


# ============================================================
# MY TRANSACTIONS — per-user flat list of fee payments
# ============================================================

class MyTransactionsView(APIView):
    """
    Return the authenticated user's own fee payments — listing fees,
    boosts, and reservation deposits — as a single flat list.
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="My transactions",
        description=(
            "Miamala yako yote — listing fees, boosts, na reservations — "
            "kama orodha moja ya pande zote."
        ),
        responses=MyTransactionSerializer(many=True),
    )
    def get(self, request):
        user = request.user
        records = []

        # ---- Listing fees ----
        for item in ListingFee.objects.filter(
            seller=user
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
                "method": "—",
                "paid_at": item.paid_at,
                "created_at": item.created_at,
            })

        # ---- Boosts ----
        for item in ListingBoost.objects.filter(
            seller=user
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
                "method": "—",
                "paid_at": item.paid_at,
                "created_at": item.created_at,
            })

        # ---- Reservation deposits (user is the buyer) ----
        for item in Reservation.objects.filter(
            transaction__buyer=user
        ).select_related(
            "transaction", "transaction__listing"
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
                "method": "—",
                "paid_at": item.paid_at,
                "created_at": item.created_at,
            })

        records.sort(
            key=lambda r: r["created_at"],
            reverse=True,
        )

        serializer = MyTransactionSerializer(records, many=True)

        return Response(
            {
                "count": len(records),
                "results": serializer.data,
            }
        )

    @staticmethod
    def _map_status(payment_status):
        mapping = {
            "PAID": "completed",
            "PENDING": "pending",
            "FAILED": "failed",
            "REFUNDED": "refunded",
        }
        return mapping.get(payment_status, "pending")