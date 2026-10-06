from django.urls import path

from .api import (
    order_status_view,
    PayoutCreateView,
    PayoutDetailView,
    PayoutListCreateView,
    PayoutSyncView,
    transactions_view,
)
from .views import fimipay_webhook


urlpatterns = [
    # NOTE: create_order / order_status are intentionally NOT routed.
    # Every payment initiation goes through app-specific services
    # (initiate_boost_payment, initiate_purchase_payment, etc.) which
    # use the DB-stored amount, never client input.

    # Merchant transactions (read-only, staff-only)
    # Scoped polling endpoint — frontend polls this after a payment is
    # initiated. Restricted to the order's owner (or staff).
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
