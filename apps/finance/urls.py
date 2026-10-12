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
from .views_receipt import TransactionReceiptView
from .views_sync import (
    SyncAllPendingView,
    SyncUserPendingView,
    SyncMeView,
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
    # Receipt per transaction
    # ═══════════════════════════════════════════════════════════
    path(
        "transactions/<int:pk>/receipt/",
        TransactionReceiptView.as_view(),
        name="transaction-receipt",
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
    # Manual FimiPay sync
    # ═══════════════════════════════════════════════════════════
    path(
        "sync/all/",
        SyncAllPendingView.as_view(),
        name="sync-all",
    ),
    path(
        "sync/me/",
        SyncMeView.as_view(),
        name="sync-me",
    ),
    path(
        "sync/user/<int:user_id>/",
        SyncUserPendingView.as_view(),
        name="sync-user",
    ),

    # ═══════════════════════════════════════════════════════════
    # Toggles router
    # ═══════════════════════════════════════════════════════════
    path("", include(router.urls)),
]