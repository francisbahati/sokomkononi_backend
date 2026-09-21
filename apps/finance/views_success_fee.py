from decimal import Decimal
from uuid import uuid4

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView


class SuccessFeeView(APIView):
    """
    POST /api/finance/success-fee/

    Records a small fee (e.g. CSV download). Simulated for now;
    can be wired to a payment gateway later.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        purpose = (request.data.get("purpose") or "").strip()
        amount_raw = request.data.get("amount")
        currency = (request.data.get("currency") or "TZS").strip().upper()

        if not purpose:
            return Response(
                {"detail": "purpose inahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = Decimal(str(amount_raw))
        except Exception:
            return Response(
                {"detail": "amount si sahihi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount <= Decimal("0"):
            return Response(
                {"detail": "amount lazima iwe kubwa kuliko sifuri."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reference = f"SF-{uuid4().hex[:12].upper()}"

        return Response(
            {
                "detail": "Malipo yamekamilika.",
                "reference": reference,
                "purpose": purpose,
                "amount": str(amount),
                "currency": currency,
                "status": "PAID",
                "user_id": request.user.id,
            },
            status=status.HTTP_200_OK,
        )
