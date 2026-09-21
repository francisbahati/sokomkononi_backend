from django.urls import path

from .views_admin_reports import (
    ConversionRateView,
    DealsStatusView,
    ListingsGrowthView,
    MostViewedListingsView,
    ReportsOverviewView,
    RevenueByMonthView,
    TopCategoriesView,
    TopLocationsView,
    TopSellersView,
    UsersGrowthView,
)


urlpatterns = [
    path("overview/", ReportsOverviewView.as_view(), name="reports-overview"),
    path("users-growth/", UsersGrowthView.as_view(), name="reports-users-growth"),
    path("listings-growth/", ListingsGrowthView.as_view(), name="reports-listings-growth"),
    path("revenue-by-month/", RevenueByMonthView.as_view(), name="reports-revenue-by-month"),
    path("deals-status/", DealsStatusView.as_view(), name="reports-deals-status"),
    path("top-sellers/", TopSellersView.as_view(), name="reports-top-sellers"),
    path("most-viewed-listings/", MostViewedListingsView.as_view(), name="reports-most-viewed-listings"),
    path("top-categories/", TopCategoriesView.as_view(), name="reports-top-categories"),
    path("top-locations/", TopLocationsView.as_view(), name="reports-top-locations"),
    path("conversion-rate/", ConversionRateView.as_view(), name="reports-conversion-rate"),
]
