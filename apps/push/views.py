# apps/push/views.py
"""
Endpoints za push subscription.

POST /api/push/subscribe/    — sajili kifaa
POST /api/push/unsubscribe/  — ondoa kifaa
"""
import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PushSubscription

logger = logging.getLogger(__name__)


class PushSubscribeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        endpoint = (request.data.get("endpoint") or "").strip()
        keys = request.data.get("keys") or {}
        p256dh = (keys.get("p256dh") or "").strip()
        auth = (keys.get("auth") or "").strip()

        if not (endpoint and p256dh and auth):
            return Response(
                {"detail": "endpoint + keys.p256dh + keys.auth zinahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # upsert: kama endpoint ipo tayari (kifaa kilekile), sasisha user
        obj, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": p256dh,
                "auth": auth,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
            },
        )

        return Response(
            {
                "ok": True,
                "created": created,
                "subscription_id": obj.id,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PushUnsubscribeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        endpoint = (request.data.get("endpoint") or "").strip()
        if not endpoint:
            return Response(
                {"detail": "endpoint inahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted, _ = (
            PushSubscription.objects
            .filter(user=request.user, endpoint=endpoint)
            .delete()
        )

        return Response(
            {"ok": True, "deleted": deleted},
            status=status.HTTP_200_OK,
        )