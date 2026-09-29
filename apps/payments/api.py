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

from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
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
    serializer = OrderStatusSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = get_order_status(serializer.validated_data["order_id"])
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


class PayoutListCreateView(APIView):
    """
    GET  /api/payments/payouts/    list every payout (staff)
    POST /api/payments/payouts/create/  request a payout (staff)
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        qs = Payout.objects.select_related("created_by").all()
        page = self.paginate_queryset(qs) if hasattr(self, "paginate_queryset") else None
        serializer = PayoutSerializer(qs, many=True)
        return Response(serializer.data)


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
