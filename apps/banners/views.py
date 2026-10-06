from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.credits.services import consume_credit

from .models import BannerAd
from .serializers import (
    BannerAdCreateSerializer,
    BannerAdSerializer,
)


class BannerAdViewSet(viewsets.ModelViewSet):
    queryset = BannerAd.objects.select_related("listing", "seller")
    serializer_class = BannerAdSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return BannerAd.objects.none()

        user = self.request.user
        qs = BannerAd.objects.select_related("listing", "seller")

        # Public: only active banners
        if not user or not user.is_authenticated:
            return qs.filter(
                active=True,
                expires_at__gt=timezone.now(),
            )

        # Staff sees everything
        if user.is_staff:
            return qs

        # Sellers see their own + active public banners
        return qs.filter(
            Q(seller=user) | Q(active=True, expires_at__gt=timezone.now())
        ).distinct()

    def create(self, request, *args, **kwargs):
        serializer = BannerAdCreateSerializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        from .services import create_banner_ad

        # SASISHO: `create_banner_ad()` service inatarajia `listing_id` + `seller`,
        # sio `listing` + `user`.
        banner = create_banner_ad(
            listing_id=serializer.validated_data["listing"],
            seller=request.user,
        )

        return Response(
            BannerAdSerializer(banner, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        banner = BannerAd.objects.filter(pk=pk).first()
        if not banner:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if banner.seller_id != request.user.id and not request.user.is_staff:
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Credits path ──────────────────────────────────────────
        payment_reference = (request.data.get("payment_reference") or "").strip()
        if payment_reference == "credits":
            import uuid
            from django.db import transaction
            from .services import _get_ad_fee_config

            with transaction.atomic():
                if not consume_credit(request.user, "ads"):
                    return Response(
                        {"detail": "Hakuna ads credits za kutosha."},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
                cfg = _get_ad_fee_config()
                banner.payment_status = "PAID"
                banner.payment_reference = (
                    f"credits-{banner.pk}-{uuid.uuid4().hex[:12]}"
                )
                banner.paid_at = timezone.now()
                banner.active = True
                banner.expires_at = (
                    timezone.now() + timedelta(days=cfg.days)
                )
                banner.save(update_fields=[
                    "payment_status", "payment_reference",
                    "paid_at", "active", "expires_at",
                ])
            return Response(
                {
                    "payment_status": "SUCCESS",
                    "via": "credits",
                    "banner": BannerAdSerializer(
                        banner, context={"request": request}
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        # ── Default: FimiPay ──────────────────────────────────────
        from .services import initiate_banner_payment
        data = initiate_banner_payment(
            banner=banner, user=request.user,
            payment_method=request.data.get("payment_method", "mobile"),
            phone=request.data.get("phone", ""),
        )
        return Response({
            "banner_id": banner.id,
            "payment_status": (data.get("payment_status") or "PENDING"),
            "fimipay": data,
        }, status=status.HTTP_201_CREATED)