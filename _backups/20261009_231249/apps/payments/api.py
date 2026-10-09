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
from django.shortcuts import get_object_or_404

from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
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
@permission_classes([permissions.IsAuthenticated])
def create_order_view(request):
    serializer = CreateOrderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = create_order(**serializer.validated_data)
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def order_status_view(request):
    from .order_ids import parse_order_id
    serializer = OrderStatusSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    order_id = serializer.validated_data["order_id"]

    prefix, ref_id = parse_order_id(order_id)
    if not prefix or ref_id is None:
        return Response({"detail": "order_id si sahihi."}, status=400)

    if not _user_owns_order(request.user, prefix, ref_id):
        return Response({"detail": "Haipatikani."}, status=404)

    data = get_order_status(order_id)
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
    """Map FimiPay status to our enum and update the row in place."""
    raw = (data.get("status") or "").lower()
    mapping = {
        "pending": Payout.Status.PENDING,
        "processing": Payout.Status.PROCESSING,
        "completed": Payout.Status.COMPLETED,
        "success": Payout.Status.COMPLETED,
        "failed": Payout.Status.FAILED,
        "rejected": Payout.Status.REJECTED,
    }
    new_status = mapping.get(raw, payout.status)
    changed = False
    if payout.status != new_status:
        payout.status = new_status
        changed = True
    if payout.fimi_status != raw:
        payout.fimi_status = raw
        changed = True
    if data != payout.raw_response:
        payout.raw_response = data
        changed = True
    from django.utils import timezone
    payout.last_synced_at = timezone.now()
    changed = True
    if changed:
        payout.save()


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
        return Response(
            PayoutSerializer(payout).data,
            status=status.HTTP_201_CREATED,
        )


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
