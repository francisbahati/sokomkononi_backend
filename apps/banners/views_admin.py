# apps/banners/views_admin.py
from datetime import timedelta

from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.banners.models import BannerAd
from apps.boosting.models import ListingBoost
from apps.listings.models import Listing


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class AdminPromotionsView(APIView):
    """
    GET /api/admin/promotions/
    Aggregated view of boosted / leading / advertised listings + campaigns.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()

        # ---------- Boosted ----------
        boosts = (
            ListingBoost.objects
            .filter(status=ListingBoost.BoostStatus.ACTIVE, expires_at__gt=now)
            .select_related("listing", "seller")
        )
        boosted = []
        for b in boosts:
            days_remaining = max(
                0, (b.expires_at - now).days
            )
            boosted.append({
                "id": b.id,
                "title": b.listing.title,
                "category": getattr(b.listing.category, "slug", ""),
                "price": float(b.listing.price),
                "seller_name": b.seller.name,
                "seller": b.seller.name,
                "promotionType": "boost",
                "daysRemaining": days_remaining,
                "amount": float(b.amount or 0),
            })

        # ---------- Advertised (banner) ----------
        banners = BannerAd.objects.filter(
            active=True, expires_at__gt=now,
        )
        advertised = []
        for b in banners:
            days_remaining = max(0, (b.expires_at - now).days)
            advertised.append({
                "id": b.id,
                "title": b.listing_title,
                "category": b.category,
                "price": float(b.price or 0),
                "seller_name": b.seller_name,
                "seller": b.seller_name,
                "promotionType": "advertise",
                "daysRemaining": days_remaining,
                "amount": float(b.amount or 0),
            })

        # ---------- Leading (currently no model — placeholder) ----------
        leading = []

        # ---------- Campaigns (no model — placeholder) ----------
        campaigns = []

        # ---------- Revenue by type ----------
        boost_revenue = sum(b["amount"] for b in boosted)
        ads_revenue = sum(a["amount"] for a in advertised)
        leading_revenue = sum(l.get("amount", 0) for l in leading)

        return Response({
            "counts": {
                "boosted": len(boosted),
                "leading": len(leading),
                "advertised": len(advertised),
                "campaigns": len(campaigns),
            },
            "boostedListings": boosted,
            "leadingListings": leading,
            "advertisedListings": advertised,
            "campaigns": campaigns,
            "revenueByType": {
                "boost": boost_revenue,
                "leading": leading_revenue,
                "advertise": ads_revenue,
            },
            "totalPromotionRevenue": boost_revenue + ads_revenue + leading_revenue,
        })
