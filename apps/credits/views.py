from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import UserCredit, UserService
from .serializers import (
    ConsumeCreditSerializer,
    UserCreditSerializer,
    UserServiceSerializer,
)
from .services import consume_credit, has_service


class UserCreditViewSet(viewsets.GenericViewSet):
    """
    User-scoped credit endpoints.

        GET  /api/credits/                 list my balances
        GET  /api/credits/services/        list my active services
        GET  /api/credits/has/<service>/   is service active for me?
        POST /api/credits/consume/         self-consume my credits
        POST /api/credits/me/consume/      (alias — canonical)
    """
    serializer_class = UserCreditSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        qs = UserCredit.objects.filter(user=request.user)
        return Response(UserCreditSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="services")
    def my_services(self, request):
        qs = UserService.objects.filter(user=request.user)
        return Response(UserServiceSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path=r"has/(?P<service>[^/.]+)")
    def check_service(self, request, service=None):
        return Response({
            "service": service,
            "has": has_service(request.user, service),
        })

    # --------------------------------------------------------
    # SELF-CONSUME — the frontend calls this
    # --------------------------------------------------------
    def _consume(self, request):
        service_key = (request.data.get("service_key") or "").strip()
        try:
            amount = int(request.data.get("amount", 1))
        except (TypeError, ValueError):
            amount = 1

        if not service_key:
            return Response(
                {"detail": "service_key inahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if amount < 1:
            return Response(
                {"detail": "amount lazima iwe angalau 1."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Idempotency: honour Idempotency-Key header
        from django.core.cache import cache
        idem = request.META.get("HTTP_IDEMPOTENCY_KEY")
        cache_key = (
            f"credits_consume:{request.user.id}:{service_key}:{idem}"
            if idem else None
        )
        if cache_key:
            cached = cache.get(cache_key)
            if cached:
                return Response(cached, status=status.HTTP_200_OK)

        ok = consume_credit(request.user, service_key, amount)
        if not ok:
            return Response(
                {
                    "detail": f"Hakuna {service_key} credits za kutosha.",
                    "code": "insufficient_credits",
                    "service_key": service_key,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        try:
            credit = UserCredit.objects.get(
                user=request.user, service_key=service_key,
            )
            payload = {
                "service_key": service_key,
                "remaining": credit.remaining,
                "total": credit.total,
                "consumed": amount,
            }
        except UserCredit.DoesNotExist:
            payload = {
                "service_key": service_key,
                "remaining": 0,
                "total": 0,
                "consumed": amount,
            }

        if cache_key:
            cache.set(cache_key, payload, timeout=300)
        return Response(payload, status=status.HTTP_200_OK)

    @action(
        detail=False, methods=["post"],
        url_path="consume",
        permission_classes=[permissions.IsAuthenticated],
    )
    def consume(self, request):
        return self._consume(request)

    @action(
        detail=False, methods=["post"],
        url_path="me/consume",
        permission_classes=[permissions.IsAuthenticated],
    )
    def me_consume(self, request):
        return self._consume(request)
