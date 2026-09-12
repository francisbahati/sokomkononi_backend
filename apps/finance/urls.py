
from django.urls import path

from .views import (
    FinancialDashboardView,
    RevenueReportView,
)


urlpatterns = [
    path(
        "dashboard/",
        FinancialDashboardView.as_view(),
        name="financial-dashboard",
    ),
    path(
        "revenue/",
        RevenueReportView.as_view(),
        name="revenue-report",
    ),
]

