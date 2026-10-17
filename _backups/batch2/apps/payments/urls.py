from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .api import (
    order_status_view,
    PayoutCreateView,
    PayoutDetailView,
    PayoutListCreateView,
    PayoutSyncView,
    transactions_view,
)
from .views import fimipay_webhook
from .views_refunds import RefundViewSet


# ============================================================
# REFUNDS ROUTER
# ============================================================
refunds_router = SimpleRouter()
refunds_router.register(
    r"refunds", RefundViewSet, basename="refund",
)


# ============================================================
# URL PATTERNS
# ============================================================
urlpatterns = [
    # ── FimiPay — order status + transactions ──────────────
    path("order-status/", order_status_view, name="fimipay-order-status"),
    path("transactions/", transactions_view, name="fimipay-transactions"),

    # ── Payouts ────────────────────────────────────────────
    path("payouts/", PayoutListCreateView.as_view(), name="fimipay-payouts"),
    path("payouts/create/", PayoutCreateView.as_view(), name="fimipay-payouts-create"),
    path("payouts/<int:pk>/", PayoutDetailView.as_view(), name="fimipay-payout-detail"),
    path("payouts/<int:pk>/sync/", PayoutSyncView.as_view(), name="fimipay-payout-sync"),

    # ── Webhook (called by FimiPay) ────────────────────────
    path("webhook/", fimipay_webhook, name="fimipay-webhook"),

    # ── Refunds ────────────────────────────────────────────
    path("", include(refunds_router.urls)),
]