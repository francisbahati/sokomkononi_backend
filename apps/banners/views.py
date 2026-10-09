# apps/banners/views.py
from datetime import timedelta

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.credits.services import consume_credit

from .models import BannerAd, Campaign
from .serializers import (
    BannerAdCreateSerializer,
    BannerAdSerializer,
    CampaignSerializer,
)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class BannerAdViewSet(viewsets.ModelViewSet):
    queryset = BannerAd.objects.select_related("listing", "seller", "package")
    serializer_class = BannerAdSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return BannerAd.objects.none()

        user = self.request.user
        qs = BannerAd.objects.select_related("listing", "seller", "package")

        if not user or not user.is_authenticated:
            return qs.filter(
                active=True,
                expires_at__gt=timezone.now(),
            )

        if user.is_staff:
            return qs

        return qs.filter(
            Q(seller=user) | Q(active=True, expires_at__gt=timezone.now())
        ).distinct()

    def create(self, request, *args, **kwargs):
        serializer = BannerAdCreateSerializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        from .services import create_banner_ad

        banner = create_banner_ad(
            listing_id=serializer.validated_data["listing"],
            seller=request.user,
            package=serializer.validated_data["package"],
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

        payment_reference = (request.data.get("payment_reference") or "").strip()

        # ============================================================
        # ✅ MPYA — "free" branch
        # Admin akizima advertisement fee, seller anaweza kutuma
        # payment_reference="free" ili ku-activate banner moja kwa moja.
        # ============================================================
        if payment_reference == "free":
            # Angalia kama advertisement fee imezimwa.
            # Kama bado inatumika, kataa — mtu asitumie "free" kudanganya.
            try:
                from apps.advertisement_fees.models import (
                    AdvertisementFeeConfig,
                )
                cfg = AdvertisementFeeConfig.objects.first()
                if cfg and cfg.is_enabled:
                    return Response(
                        {
                            "detail": (
                                "Advertisement fee bado inatumika. "
                                "Hauwezi kutumia 'free'."
                            ),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception:
                # Kama app haipo, tunaendelea — kwa sababu mfumo
                # hauwezi kuangalia. Bora kuruhusu kuliko kukataa.
                pass

            import uuid

            hours = banner.package.duration_hours if banner.package else 168
            banner.payment_status = "PAID"
            banner.payment_reference = (
                f"free-{banner.pk}-{uuid.uuid4().hex[:12]}"
            )
            banner.paid_at = timezone.now()
            banner.active = True
            banner.expires_at = timezone.now() + timedelta(hours=hours)
            banner.save(update_fields=[
                "payment_status", "payment_reference",
                "paid_at", "active", "expires_at",
            ])

            return Response(
                {
                    "payment_status": "SUCCESS",
                    "via": "free",
                    "banner": BannerAdSerializer(
                        banner, context={"request": request}
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        # ============================================================
        # "credits" branch — seller anatumia credits
        # ============================================================
        if payment_reference == "credits":
            import uuid
            from django.db import transaction

            with transaction.atomic():
                if not consume_credit(request.user, "ads"):
                    return Response(
                        {"detail": "Hakuna ads credits za kutosha."},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
                hours = banner.package.duration_hours if banner.package else 168
                banner.payment_status = "PAID"
                banner.payment_reference = (
                    f"credits-{banner.pk}-{uuid.uuid4().hex[:12]}"
                )
                banner.paid_at = timezone.now()
                banner.active = True
                banner.expires_at = timezone.now() + timedelta(hours=hours)
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

        # ============================================================
        # FimiPay — malipo halisi
        # ============================================================
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


# ============================================================
# CAMPAIGN VIEWSET
# ============================================================
class CampaignViewSet(viewsets.ModelViewSet):
    """
    GET    /api/banners/campaigns/             → list
    POST   /api/banners/campaigns/             → create (admin)
    PATCH  /api/banners/campaigns/{id}/        → update (admin)
    DELETE /api/banners/campaigns/{id}/        → delete (admin)
    POST   /api/banners/campaigns/{id}/toggle/ → toggle active (admin)
    """
    serializer_class = CampaignSerializer
    permission_classes = [IsAdminOrReadOnly]
    queryset = Campaign.objects.all()

    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, pk=None):
        campaign = self.get_object()
        campaign.active = not campaign.active
        campaign.save(update_fields=["active", "updated_at"])
        return Response({"active": campaign.active})


# ============================================================
# PROMOTIONS ANALYTICS
# ============================================================
class PromotionsAnalyticsView(viewsets.ViewSet):
    """
    GET /api/banners/analytics/

    Inarudisha counts za promotions kwa PromotionsSection:
      - boostedListings: ListingBoost zilizo ACTIVE
      - leadingListings: ListingLeading zilizo ACTIVE
      - advertisedListings: BannerAd zilizo active
      - reservedListings: Reserved listings (kutoka transactions)
      - successFeeDeals: Success fee payments
      - listingFeeTransactions: ListingFee zilizolipwa
      - counts: {boosted, leading, advertised, reserved, successFee, listingFee, campaigns, totalActive}
    """
    permission_classes = [permissions.IsAdminUser]

    def list(self, request):
        now = timezone.now()
        results = {
            "boostedListings": [],
            "leadingListings": [],
            "advertisedListings": [],
            "reservedListings": [],
            "successFeeDeals": [],
            "listingFeeTransactions": [],
            "counts": {
                "boosted": 0,
                "leading": 0,
                "advertised": 0,
                "reserved": 0,
                "successFee": 0,
                "listingFee": 0,
                "campaigns": 0,
                "totalActive": 0,
            },
            "topPromotedSellers": [],
            "source": "api",
        }

        # ── BOOSTED ────────────────────────────────────────
        try:
            from apps.boosting.models import ListingBoost
            boosts = (
                ListingBoost.objects
                .filter(
                    status=ListingBoost.BoostStatus.ACTIVE,
                    expires_at__gt=now,
                )
                .select_related("listing", "seller", "package")
                .order_by("-created_at")[:100]
            )
            results["boostedListings"] = [
                {
                    "id": b.id,
                    "listingId": b.listing_id,
                    "title": b.listing.title if b.listing else "",
                    "category": getattr(b.listing.category, "slug", "") if b.listing else "",
                    "seller_name": b.seller.name if b.seller else "",
                    "amount": float(b.amount or 0),
                    "daysRemaining": max(0, (b.expires_at - now).days) if b.expires_at else 0,
                    "date": b.created_at.isoformat() if b.created_at else None,
                }
                for b in boosts
            ]
            results["counts"]["boosted"] = len(results["boostedListings"])
        except Exception:
            pass

        # ── LEADING ────────────────────────────────────────
        try:
            from apps.leading_fees.models import ListingLeading
            leadings = (
                ListingLeading.objects
                .filter(
                    status=ListingLeading.Status.ACTIVE,
                    expires_at__gt=now,
                )
                .select_related("listing", "seller", "package")
                .order_by("-created_at")[:100]
            )
            results["leadingListings"] = [
                {
                    "id": l.id,
                    "listingId": l.listing_id,
                    "title": l.listing.title if l.listing else "",
                    "category": getattr(l.listing.category, "slug", "") if l.listing else "",
                    "seller_name": l.seller.name if l.seller else "",
                    "amount": float(l.price or 0),
                    "daysRemaining": max(0, (l.expires_at - now).days) if l.expires_at else 0,
                    "date": l.created_at.isoformat() if l.created_at else None,
                }
                for l in leadings
            ]
            results["counts"]["leading"] = len(results["leadingListings"])
        except Exception:
            pass

        # ── ADVERTISED ─────────────────────────────────────
        try:
            banners = (
                BannerAd.objects
                .filter(active=True, expires_at__gt=now)
                .select_related("listing", "seller", "package")
                .order_by("-created_at")[:100]
            )
            results["advertisedListings"] = [
                {
                    "id": b.id,
                    "listingId": b.listing_id,
                    "title": b.listing_title or "",
                    "category": b.category or "",
                    "seller_name": b.seller_name or "",
                    "amount": float(b.amount or 0),
                    "daysRemaining": max(0, (b.expires_at - now).days) if b.expires_at else 0,
                    "date": b.created_at.isoformat() if b.created_at else None,
                }
                for b in banners
            ]
            results["counts"]["advertised"] = len(results["advertisedListings"])
        except Exception:
            pass

        # ── SUCCESS FEE ────────────────────────────────────
        try:
            from apps.finance.models import SuccessFeePayment
            fees = (
                SuccessFeePayment.objects
                .filter(payment_status="PAID")
                .select_related("user")
                .order_by("-created_at")[:100]
            )
            results["successFeeDeals"] = [
                {
                    "id": s.id,
                    "title": f"Report download — {s.user.name if s.user else ''}",
                    "seller_name": s.user.name if s.user else "",
                    "amount": float(s.amount or 0),
                    "date": s.created_at.isoformat() if s.created_at else None,
                }
                for s in fees
            ]
            results["counts"]["successFee"] = len(results["successFeeDeals"])
        except Exception:
            pass

        # ── LISTING FEE ────────────────────────────────────
        try:
            from apps.listings.models import ListingFee
            listing_fees = (
                ListingFee.objects
                .filter(payment_status="PAID")
                .select_related("listing", "seller")
                .order_by("-created_at")[:100]
            )
            results["listingFeeTransactions"] = [
                {
                    "id": lf.id,
                    "title": lf.listing.title if lf.listing else "",
                    "seller_name": lf.seller.name if lf.seller else "",
                    "amount": float(lf.amount or 0),
                    "date": lf.paid_at.isoformat() if lf.paid_at else lf.created_at.isoformat(),
                }
                for lf in listing_fees
            ]
            results["counts"]["listingFee"] = len(results["listingFeeTransactions"])
        except Exception:
            pass

        # ── CAMPAIGNS ──────────────────────────────────────
        try:
            results["counts"]["campaigns"] = Campaign.objects.filter(
                active=True,
            ).count()
        except Exception:
            pass

        results["counts"]["totalActive"] = (
            results["counts"]["boosted"]
            + results["counts"]["leading"]
            + results["counts"]["advertised"]
        )

        return Response(results)