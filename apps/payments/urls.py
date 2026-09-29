from django.urls import path

from .api import (
    PayoutCreateView,
    PayoutDetailView,
    PayoutListCreateView,
    PayoutSyncView,
    create_order_view,
    order_status_view,
    transactions_view,
)
from .views import fimipay_webhook


urlpatterns = [
    # Collections
    path("create-order/", create_order_view, name="fimipay-create-order"),
    path("order-status/", order_status_view, name="fimipay-order-status"),

    # Merchant transactions (read-only, staff-only)
    path("transactions/", transactions_view, name="fimipay-transactions"),

    # Payouts
    path("payouts/", PayoutListCreateView.as_view(), name="fimipay-payouts"),
    path("payouts/create/", PayoutCreateView.as_view(), name="fimipay-payouts-create"),
    path("payouts/<int:pk>/", PayoutDetailView.as_view(), name="fimipay-payout-detail"),
    path("payouts/<int:pk>/sync/", PayoutSyncView.as_view(), name="fimipay-payout-sync"),

    # Webhook (called by FimiPay)
    path("webhook/", fimipay_webhook, name="fimipay-webhook"),
]
