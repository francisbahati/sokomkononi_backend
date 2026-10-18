"""Per-endpoint admin report routes.

Each endpoint reuses ReportsView (aggregated) and returns a slice.
"""
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.urls import path


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


def _aggregate(request):
    from .views_reports import ReportsView
    return ReportsView().get(request).data


class UsersGrowthView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response(_aggregate(request).get("usersGrowth", []))


class ListingsGrowthView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response(_aggregate(request).get("listingsGrowth", []))


class RevenueByMonthView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response(_aggregate(request).get("revenueByMonth", []))


class DealsStatusView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response(_aggregate(request).get("dealsByStatus", {}))


class TopSellersView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response(_aggregate(request).get("topSellers", []))


class MostViewedView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response(_aggregate(request).get("mostViewedListings", []))


class TopCategoriesView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response(_aggregate(request).get("topCategories", []))


class TopLocationsView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response(_aggregate(request).get("topLocations", []))


class ConversionRateView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response({"rate": _aggregate(request).get("conversionRate", 0)})


urlpatterns = [
    path("users-growth/", UsersGrowthView.as_view(), name="admin-reports-users-growth"),
    path("listings-growth/", ListingsGrowthView.as_view(), name="admin-reports-listings-growth"),
    path("revenue-by-month/", RevenueByMonthView.as_view(), name="admin-reports-revenue-month"),
    path("deals-status/", DealsStatusView.as_view(), name="admin-reports-deals-status"),
    path("top-sellers/", TopSellersView.as_view(), name="admin-reports-top-sellers"),
    path("most-viewed-listings/", MostViewedView.as_view(), name="admin-reports-most-viewed"),
    path("top-categories/", TopCategoriesView.as_view(), name="admin-reports-top-categories"),
    path("top-locations/", TopLocationsView.as_view(), name="admin-reports-top-locations"),
    path("conversion-rate/", ConversionRateView.as_view(), name="admin-reports-conversion"),
]
