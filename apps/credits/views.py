from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import UserCredit, UserService
from .serializers import (
    UserCreditSerializer,
    UserServiceSerializer,
)
from .services import has_service


class UserCreditViewSet(viewsets.GenericViewSet):
    """
    Public credit view — read-only. Internal services consume credits
    directly; there is NO public consume endpoint.
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

    @action(detail=False, methods=["post"], url_path="consume")
    def consume(self, request):
        """
        POST /api/credits/consume/
        Body: { "service_key": "boost", "amount": 1 }

        Idempotency: pass `Idempotency-Key` header. Replays with the
        same key return the same response without double-decrement.
        """
        from .services import consume_credit
        from .models import UserCredit

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

        # Idempotency cache (in-process, per-worker).
        idem_key = request.META.get("HTTP_IDEMPOTENCY_KEY")
        cache = getattr(self, "_idem_cache", None)
        if cache is None:
            from django.core.cache import cache as _djcache
            cache = _djcache
            self._idem_cache = cache

        cache_key = f"credits_consume:{request.user.id}:{idem_key}" if idem_key else None
        if cache_key:
            cached = cache.get(cache_key)
            if cached:
                return Response(cached, status=status.HTTP_200_OK)

        ok = consume_credit(request.user, service_key, amount)
        if not ok:
            return Response(
                {"detail": f"Hakuna {service_key} credits za kutosha."},
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
            }
        except UserCredit.DoesNotExist:
            payload = {
                "service_key": service_key,
                "remaining": 0,
                "total": 0,
            }

        if cache_key:
            cache.set(cache_key, payload, timeout=300)
        return Response(payload, status=status.HTTP_200_OK)
