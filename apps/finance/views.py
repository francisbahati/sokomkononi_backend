
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
)
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    FinancialDashboardSerializer,
    RevenueRecordSerializer,
)
from .services.revenue import (
    calculate_financial_dashboard,
    get_revenue_records,
)


class IsAdminUser(permissions.BasePermission):
    """
    Only Django staff/admin users can access financial information.
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
        description=(
            "Inaonyesha muhtasari wa mapato ya SokoMkononi "
            "kutoka Listing Fees, Reservation Fees na Boosting Fees."
        ),
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
        period = request.query_params.get(
            "period",
            "all",
        )

        if period not in {
            "all",
            "today",
            "week",
            "month",
        }:
            return Response(
                {
                    "detail": (
                        "Invalid period. "
                        "Use all, today, week, or month."
                    )
                },
                status=400,
            )

        data = calculate_financial_dashboard(
            period
        )

        serializer = FinancialDashboardSerializer(
            data
        )

        return Response(serializer.data)


class RevenueReportView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Detailed revenue report",
        description=(
            "Inaonyesha kila malipo ya SokoMkononi "
            "kwa chanzo, kiasi, seller, listing, "
            "payment reference na tarehe."
        ),
        parameters=[
            OpenApiParameter(
                name="period",
                type=str,
                required=False,
                enum=[
                    "all",
                    "today",
                    "week",
                    "month",
                ],
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
        period = request.query_params.get(
            "period",
            "all",
        )

        source = request.query_params.get(
            "source",
            "all",
        )

        valid_periods = {
            "all",
            "today",
            "week",
            "month",
        }

        valid_sources = {
            "all",
            "listing_fee",
            "reservation",
            "boosting",
            "refund",
        }

        if period not in valid_periods:
            return Response(
                {
                    "detail": (
                        "Invalid period. "
                        "Use all, today, week, or month."
                    )
                },
                status=400,
            )

        if source not in valid_sources:
            return Response(
                {
                    "detail": (
                        "Invalid source. "
                        "Use all, listing_fee, reservation, "
                        "boosting, or refund."
                    )
                },
                status=400,
            )

        records = get_revenue_records(
            period=period,
            source=source,
        )

        serializer = RevenueRecordSerializer(
            records,
            many=True,
        )

        return Response(
            {
                "period": period,
                "source": source,
                "count": len(records),
                "results": serializer.data,
            }
        )
