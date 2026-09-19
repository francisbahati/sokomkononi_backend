# apps/finance/views_reports.py
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.deals.models import DealRoom
from apps.listings.models import Listing
from apps.transactions.models import Transaction


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class ReportsView(APIView):
    """
    GET /api/admin/reports/
    Returns dashboard aggregates for ReportsSection.jsx
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        six_months_ago = now - timedelta(days=180)

        # ---------- Users ----------
        total_users = User.all_objects.filter(is_deleted=False).count()
        total_sellers = User.all_objects.filter(
            is_deleted=False, listings__isnull=False,
        ).distinct().count()
        total_buyers = max(0, total_users - total_sellers)

        # Growth: cumulative users per day for last 30 days
        users_growth = []
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).date()
            cumulative = User.all_objects.filter(
                is_deleted=False,
                date_joined__date__lte=day,
            ).count()
            users_growth.append({
                "label": day.strftime("%d/%m"),
                "cumulative": cumulative,
            })

        # ---------- Listings ----------
        total_listings = Listing.objects.count()
        live_listings = Listing.objects.filter(
            status=Listing.Status.AVAILABLE,
        ).count()
        sold_listings = Listing.objects.filter(
            status=Listing.Status.SOLD,
        ).count()

        listings_growth = []
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).date()
            count = Listing.objects.filter(created_at__date=day).count()
            listings_growth.append({
                "label": day.strftime("%d/%m"),
                "count": count,
            })

        # ---------- Deals ----------
        total_deals = DealRoom.objects.count()
        completed_deals = DealRoom.objects.filter(
            status=DealRoom.Status.CLOSED,
        ).count()
        disputed_deals = DealRoom.objects.filter(
            status=DealRoom.Status.CANCELLED,
        ).count()

        deals_by_status = dict(
            DealRoom.objects.values_list("status")
            .annotate(c=Count("id"))
            .values_list("status", "c")
        )
        # Ensure all keys present
        for k in ["OPEN", "NEGOTIATING", "AGREED", "CANCELLED", "CLOSED"]:
            deals_by_status.setdefault(k, 0)

        # Map to frontend keys
        deals_by_status_frontend = {
            "negotiating": deals_by_status.get("NEGOTIATING", 0),
            "accepted": deals_by_status.get("AGREED", 0),
            "reserved": 0,  # computed from transactions
            "completed": deals_by_status.get("CLOSED", 0),
            "disputed": 0,
            "cancelled": deals_by_status.get("CANCELLED", 0),
        }

        # ---------- Revenue ----------
        revenue_qs = Transaction.objects.filter(
            status=Transaction.Status.COMPLETED,
        )
        total_revenue = (
            revenue_qs.aggregate(s=Sum("agreed_price"))["s"] or 0
        )

        revenue_by_month = []
        for i in range(5, -1, -1):
            month_start = (now - timedelta(days=30 * i)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0,
            )
            if month_start.month == 12:
                month_end = month_start.replace(
                    year=month_start.year + 1, month=1,
                )
            else:
                month_end = month_start.replace(month=month_start.month + 1)
            total = (
                revenue_qs.filter(
                    completed_at__gte=month_start,
                    completed_at__lt=month_end,
                ).aggregate(s=Sum("agreed_price"))["s"] or 0
            )
            revenue_by_month.append({
                "label": month_start.strftime("%b"),
                "total": float(total),
            })

        conversion_rate = (
            (completed_deals / total_deals) * 100 if total_deals else 0
        )

        # ---------- Top sellers (by views) ----------
        top_sellers_qs = (
            Listing.objects.values("seller__id", "seller__name")
            .annotate(
                views=Sum("views_count"),
                listings=Count("id"),
            )
            .order_by("-views")[:5]
        )
        top_sellers = [
            {
                "name": s["seller__name"] or "—",
                "views": s["views"] or 0,
                "listings": s["listings"],
            }
            for s in top_sellers_qs
        ]

        # ---------- Most viewed listings ----------
        most_viewed_qs = Listing.objects.order_by("-views_count")[:5]
        most_viewed = [
            {
                "id": l.id,
                "title": l.title,
                "views": l.views_count,
                "price": float(l.price),
            }
            for l in most_viewed_qs
        ]

        # ---------- Top categories ----------
        cat_qs = (
            Listing.objects.values("category__slug", "category__name")
            .annotate(count=Count("id"), views=Sum("views_count"))
            .order_by("-views")[:5]
        )
        top_categories = [
            {
                "key": c["category__slug"] or "—",
                "name": c["category__name"] or "—",
                "count": c["count"],
                "views": c["views"] or 0,
            }
            for c in cat_qs
        ]

        # ---------- Top locations ----------
        loc_qs = (
            Listing.objects.values("location")
            .annotate(count=Count("id"), views=Sum("views_count"))
            .order_by("-views")[:5]
        )
        top_locations = [
            {
                "name": l["location"] or "—",
                "count": l["count"],
                "views": l["views"] or 0,
            }
            for l in loc_qs
        ]

        return Response({
            "totalUsers": total_users,
            "totalSellers": total_sellers,
            "totalBuyers": total_buyers,
            "usersGrowth": users_growth,

            "totalListings": total_listings,
            "liveListings": live_listings,
            "soldListings": sold_listings,
            "listingsGrowth": listings_growth,

            "totalDeals": total_deals,
            "completedDeals": completed_deals,
            "disputedDeals": disputed_deals,
            "dealsByStatus": deals_by_status_frontend,

            "totalRevenue": float(total_revenue),
            "revenueByMonth": revenue_by_month,
            "conversionRate": round(conversion_rate, 2),

            "topSellers": top_sellers,
            "mostViewedListings": most_viewed,
            "topCategories": top_categories,
            "topLocations": top_locations,
        })
