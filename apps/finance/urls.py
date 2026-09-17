from django.urls import path

from .views import (
    FinancialDashboardView,
    MyTransactionsView,
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
    path(
        "my-transactions/",
        MyTransactionsView.as_view(),
        name="my-transactions",
    ),
]