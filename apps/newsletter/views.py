from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import NewsletterSubscriber
from .serializers import (
    NewsletterSubscribeSerializer,
    NewsletterUnsubscribeSerializer,
)


class NewsletterSubscribeView(APIView):
    """
    POST /api/newsletter/subscribe/   { email, lang?, source? }

    - Public. `authentication_classes = []` ili token iliyoisha muda
      isizuie mtumiaji aliyeingia kujiunga.
    - Idempotent: jibu ni lilelile iwe barua pepe ni mpya, ipo, au
      ilijiondoa awali (hakuna kufichua nani yupo kwenye orodha).
    - Throttle: scope "newsletter" (settings.DEFAULT_THROTTLE_RATES).
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "newsletter"

    def post(self, request):
        serializer = NewsletterSubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        sub, created = NewsletterSubscriber.objects.get_or_create(
            email=d["email"],
            defaults={"lang": d.get("lang", ""), "source": d.get("source", "homepage")},
        )
        if not created and not sub.is_active:
            sub.is_active = True
            sub.unsubscribed_at = None
            if d.get("lang"):
                sub.lang = d["lang"]
            sub.save(update_fields=["is_active", "unsubscribed_at", "lang"])

        return Response(
            {"ok": True, "detail": "Asante! Umejiunga na jarida letu."},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class NewsletterUnsubscribeView(APIView):
    """POST /api/newsletter/unsubscribe/   { token }  (token kutoka kwenye barua pepe)."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_scope = "newsletter"

    def post(self, request):
        serializer = NewsletterUnsubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = NewsletterSubscriber.objects.filter(
            unsubscribe_token=serializer.validated_data["token"], is_active=True,
        ).update(is_active=False, unsubscribed_at=timezone.now())
        if not updated and not NewsletterSubscriber.objects.filter(
            unsubscribe_token=serializer.validated_data["token"],
        ).exists():
            return Response(
                {"detail": "Kiungo si sahihi."}, status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"ok": True, "detail": "Umejiondoa kwenye jarida."})
