# apps/finance/views_reports.py
from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.deals.models import DealRoom
from apps.listings.models import Listing
from apps.transactions.models import Transaction

from .services.user_stats import calculate_user_stats


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


# ============================================================
# HELPERS
# ============================================================
VISIBLE_LISTING_STATUSES = [
    Listing.Status.LIVE,
    Listing.Status.RESERVED,
    Listing.Status.SOLD,
]


def _visible_listings_qs():
    """
    Listings zinazohesabiwa kwenye Reports:
    - Hazijafutwa (is_deleted=False)
    - Sio DRAFT
    """
    return Listing.objects.filter(
        is_deleted=False,
    ).exclude(
        status=Listing.Status.DRAFT,
    )


# ============================================================
# REPORTS VIEW
# ============================================================
class ReportsView(APIView):
    """
    GET /api/finance/reports/
    Returns dashboard aggregates for ReportsSection.jsx
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        now = timezone.now()

        # ---------- Users ----------
        user_stats = calculate_user_stats()

        total_users = user_stats["totalUsers"]
        total_sellers = user_stats["totalSellers"]
        total_buyers = user_stats["totalBuyers"]

        # Growth: cumulative users per day for last 30 days
        start_day = (now - timedelta(days=29)).date()
        growth_rows = dict(
            User.objects
            .filter(
                is_deleted=False,
                is_staff=False,
                date_joined__date__gte=start_day,
            )
            .annotate(d=TruncDate("date_joined"))
            .values_list("d")
            .annotate(c=Count("id"))
            .values_list("d", "c")
        )
        baseline = User.objects.filter(
            is_deleted=False,
            is_staff=False,
            date_joined__date__lt=start_day,
        ).count()
        users_growth = []
        running = baseline
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).date()
            running += growth_rows.get(day, 0)
            users_growth.append({
                "label": day.strftime("%d/%m"),
                "cumulative": running,
            })

        # ---------- Listings ----------
        visible_qs = _visible_listings_qs()

        total_listings = visible_qs.count()
        live_listings = visible_qs.filter(
            status=Listing.Status.LIVE,
        ).count()
        sold_listings = visible_qs.filter(
            status=Listing.Status.SOLD,
        ).count()

        listings_growth = []
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).date()
            count = visible_qs.filter(created_at__date=day).count()
            listings_growth.append({
                "label": day.strftime("%d/%m"),
                "count": count,
            })

        # ---------- Deals ----------
        total_deals = DealRoom.objects.count()
        completed_deals = DealRoom.objects.filter(
            status=DealRoom.Status.COMPLETED,
        ).count()
        disputed_deals = DealRoom.objects.filter(
            status=DealRoom.Status.DISPUTED,
        ).count()

        deals_by_status = dict(
            DealRoom.objects.values_list("status")
            .annotate(c=Count("id"))
            .values_list("status", "c")
        )
        for k in ["OPEN", "NEGOTIATING", "ACCEPTED",
                  "CANCELLED", "COMPLETED", "DISPUTED"]:
            deals_by_status.setdefault(k, 0)

        deals_by_status_frontend = {
            "negotiating": deals_by_status.get("NEGOTIATING", 0),
            "accepted": deals_by_status.get("ACCEPTED", 0),
            "reserved": 0,
            "completed": deals_by_status.get("COMPLETED", 0),
            "disputed": deals_by_status.get("DISPUTED", 0),
            "cancelled": deals_by_status.get("CANCELLED", 0),
        }

        # ---------- Revenue ----------
        revenue_qs = Transaction.objects.filter(
            status=Transaction.Status.COMPLETED,
        )
        total_gmv = (
            revenue_qs.aggregate(s=Sum("agreed_price"))["s"] or 0
        )

        # Actual revenue = fees only (from fee tables)
        try:
            from .services.revenue import calculate_financial_dashboard
            fees_data = calculate_financial_dashboard("all")
            total_revenue = float(fees_data["total_revenue"])
        except Exception:
            total_revenue = 0.0

        # Revenue by month (GMV)
        revenue_by_month = []
        _anchor = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0,
        )
        for i in range(5, -1, -1):
            month_start = _anchor - relativedelta(months=i)
            month_end = month_start + relativedelta(months=1)
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
            visible_qs
            .filter(seller__is_staff=False, seller__is_deleted=False)
            .values("seller__id", "seller__name")
            .annotate(
                views=Coalesce(Sum("views_count"), 0),
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
        most_viewed_qs = visible_qs.order_by("-views_count")[:5]
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
            visible_qs
            .values("category__slug", "category__name")
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
            visible_qs
            .values("location")
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
            # ── User stats ──
            "totalUsers": total_users,
            "totalSellers": total_sellers,
            "totalBuyers": total_buyers,
            "bothRoles": user_stats["bothRoles"],
            "neitherRole": user_stats["neitherRole"],
            "totalAdmins": user_stats["totalAdmins"],
            "usersGrowth": users_growth,

            # ── Listings ──
            "totalListings": total_listings,
            "liveListings": live_listings,
            "soldListings": sold_listings,
            "listingsGrowth": listings_growth,

            # ── Deals ──
            "totalDeals": total_deals,
            "completedDeals": completed_deals,
            "disputedDeals": disputed_deals,
            "dealsByStatus": deals_by_status_frontend,

            # ── Revenue ──
            "totalGMV": float(total_gmv),
            "totalRevenue": total_revenue,
            "revenueByMonth": revenue_by_month,
            "conversionRate": round(conversion_rate, 2),

            # ── Top lists ──
            "topSellers": top_sellers,
            "mostViewedListings": most_viewed,
            "topCategories": top_categories,
            "topLocations": top_locations,
        })
