from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.fimipay import create_order


class SuccessFeeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        purpose = (request.data.get("purpose") or "").strip()
        amount = request.data.get("amount")
        if not purpose or not amount:
            return Response(
                {"detail": "purpose na amount zinahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order_id = f"SF-{request.user.id}-{purpose[:20]}"
        data = create_order(
            order_id=order_id,
            amount=amount,
            buyer_phone=request.user.phone or "",
            buyer_email=request.user.email or "",
            buyer_name=request.user.name or "",
            payment_method="mobile",
        )
        return Response({"fimipay": data}, status=status.HTTP_201_CREATED)
