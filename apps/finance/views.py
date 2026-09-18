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
                enum=["all", "listing_fee", "reservation", "boosting", "refund"],
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
            "all", "listing_fee", "reservation", "boosting", "refund",
        }:
            return Response({"detail": "Invalid source."}, status=400)

        records = get_revenue_records(period=period, source=source)
        serializer = RevenueRecordSerializer(records, many=True)

        return Response({
            "period": period,
            "source": source,
            "count": len(records),
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