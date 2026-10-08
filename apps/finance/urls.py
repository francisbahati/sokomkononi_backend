# apps/finance/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    FinancialDashboardView,
    MyTransactionsView,
    RevenueReportView,
    SuccessFeeConfigView,
    SystemFeatureToggleViewSet,
    RevenueOverviewView,
    UserStatsView,
)
from .views_reports import ReportsView
from .views_success_fee import (
    SuccessFeeView,
    SuccessFeeStatusView,
    SuccessFeeDownloadView,
)


router = DefaultRouter()
router.register("toggles", SystemFeatureToggleViewSet, basename="feature-toggle")


urlpatterns = [
    # ═══════════════════════════════════════════════════════════
    # User stats
    # ═══════════════════════════════════════════════════════════
    path("user-stats/", UserStatsView.as_view(), name="user-stats"),

    # ═══════════════════════════════════════════════════════════
    # Reports
    # ═══════════════════════════════════════════════════════════
    path("reports/", ReportsView.as_view(), name="reports"),
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
    path(
        "my-transactions/",
        MyTransactionsView.as_view(),
        name="my-transactions",
    ),

    # ═══════════════════════════════════════════════════════════
    # Success Fee — FimiPay + Status + Download
    # ═══════════════════════════════════════════════════════════
    path(
        "success-fee/",
        SuccessFeeView.as_view(),
        name="success-fee",
    ),
    path(
        "success-fee/status/",
        SuccessFeeStatusView.as_view(),
        name="success-fee-status",
    ),
    path(
        "success-fee/download/",
        SuccessFeeDownloadView.as_view(),
        name="success-fee-download",
    ),

    # ═══════════════════════════════════════════════════════════
    # Success Fee Config (admin)
    # ═══════════════════════════════════════════════════════════
    path(
        "success-fee-config/",
        SuccessFeeConfigView.as_view(),
        name="success-fee-config",
    ),
    path(
        "success-fee-config/toggle/",
        SuccessFeeConfigView.as_view(),
        name="success-fee-config-toggle",
    ),

    # ═══════════════════════════════════════════════════════════
    # Revenue Overview (bulk)
    # ═══════════════════════════════════════════════════════════
    path(
        "revenue-overview/",
        RevenueOverviewView.as_view(),
        name="revenue-overview",
    ),

    # ═══════════════════════════════════════════════════════════
    # Toggles router
    # ═══════════════════════════════════════════════════════════
    path("", include(router.urls)),
]