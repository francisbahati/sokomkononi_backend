from datetime import timedelta

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from apps.boosting.models import ListingBoost

from .models import BannerAd, Campaign


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class CampaignSerializerMixin:
    @staticmethod
    def serialize(obj):
        return {
            "id": obj.id,
            "title": obj.title,
            "description": obj.description,
            "type": obj.type,
            "startDate": obj.start_date,
            "endDate": obj.end_date,
            "budget": float(obj.budget or 0),
            "spent": float(obj.spent or 0),
            "active": obj.active,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }


class PromotionsAnalyticsView(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    def list(self, request):
        now = timezone.now()

        boosts = (
            ListingBoost.objects
            .filter(status=ListingBoost.BoostStatus.ACTIVE, expires_at__gt=now)
            .select_related("listing", "seller")
        )
        boosted = []
        for b in boosts:
            days = max(0, (b.expires_at - now).days)
            boosted.append({
                "id": b.id,
                "title": b.listing.title,
                "category": getattr(b.listing.category, "slug", ""),
                "price": float(b.listing.price),
                "seller_name": b.seller.name,
                "seller": b.seller.name,
                "promotionType": "boost",
                "daysRemaining": days,
                "amount": float(b.amount or 0),
            })

        banners = BannerAd.objects.filter(active=True, expires_at__gt=now)
        advertised = []
        for b in banners:
            days = max(0, (b.expires_at - now).days)
            advertised.append({
                "id": b.id,
                "title": b.listing_title,
                "category": b.category,
                "price": float(b.price or 0),
                "seller_name": b.seller_name,
                "seller": b.seller_name,
                "promotionType": "advertise",
                "daysRemaining": days,
                "amount": float(b.amount or 0),
            })

        leading = []

        boost_revenue = sum(b["amount"] for b in boosted)
        ads_revenue = sum(a["amount"] for a in advertised)

        return Response({
            "counts": {
                "boosted": len(boosted),
                "leading": len(leading),
                "advertised": len(advertised),
                "campaigns": Campaign.objects.filter(active=True).count(),
            },
            "boostedListings": boosted,
            "leadingListings": leading,
            "advertisedListings": advertised,
            "revenueByType": {
                "boost": boost_revenue,
                "leading": 0,
                "advertise": ads_revenue,
            },
            "totalPromotionRevenue": boost_revenue + ads_revenue,
        })


class CampaignViewSet(CampaignSerializerMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return Campaign.objects.all().order_by("-created_at")

    def list(self, request):
        return Response([self.serialize(c) for c in self.get_queryset()])

    def create(self, request):
        data = request.data or {}
        obj = Campaign.objects.create(
            title=data.get("title", ""),
            description=data.get("description", ""),
            type=data.get("type", Campaign.Type.OTHER),
            start_date=data.get("startDate") or data.get("start_date"),
            end_date=data.get("endDate") or data.get("end_date"),
            budget=data.get("budget", 0) or 0,
            spent=data.get("spent", 0) or 0,
            active=data.get("active", True),
        )
        return Response(self.serialize(obj), status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        obj = Campaign.objects.filter(pk=pk).first()
        if not obj:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = request.data or {}
        mapping = {
            "title": "title",
            "description": "description",
            "type": "type",
            "startDate": "start_date",
            "endDate": "end_date",
            "start_date": "start_date",
            "end_date": "end_date",
            "budget": "budget",
            "spent": "spent",
            "active": "active",
        }
        for src, dst in mapping.items():
            if src in data:
                setattr(obj, dst, data[src])
        obj.save()
        return Response(self.serialize(obj))

    def destroy(self, request, pk=None):
        obj = Campaign.objects.filter(pk=pk).first()
        if not obj:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
