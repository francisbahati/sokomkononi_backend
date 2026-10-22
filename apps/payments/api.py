"""
Public DRF endpoints exposing FimiPay to SokoMkononi staff and users.

  POST /api/payments/create-order/       start a payment collection
  POST /api/payments/order-status/       poll a collection
  GET  /api/payments/transactions/       list merchant transactions (staff)
  POST /api/payments/payouts/create/     request a payout (staff)
  GET  /api/payments/payouts/            list payout history (staff)
  GET  /api/payments/payouts/<id>/       retrieve one payout (staff)
  POST /api/payments/payouts/<id>/sync/  force status refresh (staff)
"""
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.throttling import UserRateThrottle
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .fimipay import (
    create_order,
    get_order_status,
    list_transactions as fp_list_transactions,
    create_payout as fp_create_payout,
    get_payout_status as fp_get_payout_status,
)
from .models import Payout
from .serializers import (
    CreateOrderSerializer,
    OrderStatusSerializer,
    PayoutCreateSerializer,
    PayoutSerializer,
)




logger = logging.getLogger(__name__)


class PaymentPollThrottle(UserRateThrottle):
    """
    Polling ya order-status isiingie kwenye kikomo cha jumla cha "user"
    (kilikuwa 1000/saa) — mteja alikuwa anakwama akishakifikia.
    """
    scope = "payment_poll"

RECONCILE_ON_POLL_PREFIXES = {"LSF", "BST", "LDS", "BND", "ADV", "SFE", "RSV"}


def _reconcile_if_paid(prefix, order_id, data):
    """
    Kama FimiPay inasema SUCCESS lakini webhook haikutumia malipo,
    yatumie sasa. Kama kutumia kumeshindikana, rudisha PENDING ili
    frontend iendelee kujaribu (badala ya kuonyesha mafanikio ya uongo).
    """
    if not getattr(settings, "PAYMENTS_RECONCILE_ON_POLL", True):
        return data
    excluded = set(getattr(settings, "PAYMENTS_RECONCILE_EXCLUDE", set()) or ())
    if (
        prefix not in RECONCILE_ON_POLL_PREFIXES
        or prefix in excluded
        or not isinstance(data, dict)
    ):
        return data

    status_str = str(
        data.get("payment_status") or data.get("status") or ""
    ).upper()
    if status_str != "SUCCESS":
        return data

    from .views import OK, apply_success_from_status
    try:
        result = apply_success_from_status(order_id, data)
    except Exception:
        logger.exception("Reconcile-from-poll crashed for %s", order_id)
        result = None

    if result == OK:
        return data

    patched = dict(data)
    patched["payment_status"] = "PENDING"
    patched["reconcile_pending"] = True
    return patched


def _user_owns_order(user, prefix, ref_id):
    """Return True if `user` owns the record referenced by order_id."""
    if user.is_staff:
        return True
    try:
        if prefix == "LSF":
            from apps.listings.models import ListingFee
            return ListingFee.objects.filter(
                listing_id=ref_id, seller=user,
            ).exists()
        if prefix == "BST":
            from apps.boosting.models import ListingBoost
            return ListingBoost.objects.filter(pk=ref_id, seller=user).exists()
        if prefix == "LDS":
            from apps.leading_fees.models import ListingLeading
            return ListingLeading.objects.filter(pk=ref_id, seller=user).exists()
        if prefix == "BND":
            from apps.bundles.models import BundlePurchase
            return BundlePurchase.objects.filter(pk=ref_id, user=user).exists()
        if prefix == "ADV":
            from apps.banners.models import BannerAd
            return BannerAd.objects.filter(pk=ref_id, seller=user).exists()
        if prefix == "SFE":
            from apps.finance.models import SuccessFeePayment
            return SuccessFeePayment.objects.filter(pk=ref_id, user=user).exists()
        if prefix == "RSV":
            from apps.transactions.models import Reservation
            return Reservation.objects.filter(
                pk=ref_id, transaction__buyer=user,
            ).exists()
    except Exception:
        return False
    return False

# ============================================================
# Collections
# ============================================================

@api_view(["POST"])
@permission_classes([permissions.IsAdminUser])
def create_order_view(request):
    serializer = CreateOrderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = create_order(**serializer.validated_data)
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@throttle_classes([PaymentPollThrottle])
@permission_classes([permissions.IsAuthenticated])
def order_status_view(request):
    from .order_ids import parse_order_id
    serializer = OrderStatusSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    order_id = serializer.validated_data["order_id"]

    prefix, ref_id = parse_order_id(order_id)
    if not prefix or ref_id is None:
        return Response({"detail": "order_id si sahihi."}, status=400)

    if prefix not in RECONCILE_ON_POLL_PREFIXES:
        # Aina ya malipo isiyojulikana (mfano ripoti/credits) — haitakuwa na
        # handler ya webhook wala ukaguzi wa umiliki: malipo hayatatumika.
        logger.warning(
            "order_status: UNKNOWN order prefix %r (order_id=%s) — "
            "no ownership check / webhook handler exists for it",
            prefix, order_id,
        )

    if not _user_owns_order(request.user, prefix, ref_id):
        logger.warning(
            "order_status: ownership check failed user=%s order_id=%s",
            request.user.id, order_id,
        )
        return Response({"detail": "Haipatikani."}, status=404)

    data = get_order_status(order_id)
    data = _reconcile_if_paid(prefix, order_id, data)
    return Response(data)


# ============================================================
# Merchant transactions (staff-only — it's an account-wide view)
# ============================================================

@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def transactions_view(request):
    data = fp_list_transactions()
    return Response({"count": len(data), "results": data})


# ============================================================
# Payouts
# ============================================================

def _apply_status(payout, data):
    """Map FimiPay status to our enum and persist only changed fields."""
    from django.utils import timezone
    raw = (data.get("status") or "").lower()
    mapping = {
        "pending":    Payout.Status.PENDING,
        "processing": Payout.Status.PROCESSING,
        "completed":  Payout.Status.COMPLETED,
        "success":    Payout.Status.COMPLETED,
        "failed":     Payout.Status.FAILED,
        "rejected":   Payout.Status.REJECTED,
    }
    payout.status = mapping.get(raw, payout.status)
    payout.fimi_status = raw
    payout.raw_response = data
    payout.last_synced_at = timezone.now()
    payout.save(update_fields=[
        "status", "fimi_status", "raw_response", "last_synced_at",
    ])



class PayoutListCreateView(generics.ListAPIView):
    """
    GET  /api/payments/payouts/    list every payout (staff)
    POST /api/payments/payouts/create/  request a payout (staff)
    """
    permission_classes = [permissions.IsAdminUser]
    serializer_class = PayoutSerializer
    pagination_class = PageNumberPagination

    def get_queryset(self):
        return Payout.objects.select_related("created_by").order_by("-created_at")


class PayoutCreateView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        from django.core.cache import cache
        idem = request.META.get("HTTP_IDEMPOTENCY_KEY")
        cache_key = f"payout_create:{request.user.id}:{idem}" if idem else None
        if cache_key:
            cached = cache.get(cache_key)
            if cached:
                return Response(cached, status=status.HTTP_200_OK)

        serializer = PayoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = fp_create_payout(**serializer.validated_data)

        payout = Payout.objects.create(
            created_by=request.user,
            withdrawal_id=data.get("withdrawal_id"),
            amount=serializer.validated_data["amount"],
            fee=data.get("fee"),
            net_amount=data.get("net_amount"),
            method=serializer.validated_data["method"],
            account_number=serializer.validated_data["account_number"],
            account_name=serializer.validated_data.get("account_name", ""),
            raw_response=data,
        )
        _apply_status(payout, data)
        payload = PayoutSerializer(payout).data
        if cache_key:
            cache.set(cache_key, payload, timeout=600)
        return Response(payload, status=status.HTTP_201_CREATED)


class PayoutDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, pk):
        payout = get_object_or_404(Payout, pk=pk)
        return Response(PayoutSerializer(payout).data)


class PayoutSyncView(APIView):
    """Force-refresh a payout's status from FimiPay."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        payout = get_object_or_404(Payout, pk=pk)
        if not payout.withdrawal_id:
            return Response(
                {"detail": "Payout haina withdrawal_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = fp_get_payout_status(payout.withdrawal_id)
        _apply_status(payout, data)
        return Response(PayoutSerializer(payout).data)