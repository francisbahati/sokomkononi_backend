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


def _users_growth(now):
    out = []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).date()
        cumulative = User.all_objects.filter(
            is_deleted=False, date_joined__date__lte=day,
        ).count()
        out.append({"label": day.strftime("%d/%m"), "cumulative": cumulative})
    return out


def _listings_growth(now):
    out = []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).date()
        count = Listing.objects.filter(created_at__date=day).count()
        out.append({"label": day.strftime("%d/%m"), "count": count})
    return out


def _revenue_by_month(now):
    qs = Transaction.objects.filter(status=Transaction.Status.COMPLETED)
    out = []
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
        total = qs.filter(
            completed_at__gte=month_start, completed_at__lt=month_end,
        ).aggregate(s=Sum("agreed_price"))["s"] or 0
        out.append({"label": month_start.strftime("%b"), "total": float(total)})
    return out


class ReportsOverviewView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_users = User.all_objects.filter(is_deleted=False).count()
        total_sellers = User.all_objects.filter(
            is_deleted=False, listings__isnull=False,
        ).distinct().count()
        total_buyers = max(0, total_users - total_sellers)

        total_listings = Listing.objects.count()
        live = Listing.objects.filter(
            status=Listing.Status.AVAILABLE,
        ).count()
        sold = Listing.objects.filter(status=Listing.Status.SOLD).count()

        total_deals = DealRoom.objects.count()
        completed = DealRoom.objects.filter(
            status=DealRoom.Status.CLOSED,
        ).count()
        disputed = DealRoom.objects.filter(
            status=DealRoom.Status.CANCELLED,
        ).count()

        revenue = Transaction.objects.filter(
            status=Transaction.Status.COMPLETED,
        ).aggregate(s=Sum("agreed_price"))["s"] or 0

        conversion = (completed / total_deals * 100) if total_deals else 0

        return Response({
            "totalUsers": total_users,
            "totalSellers": total_sellers,
            "totalBuyers": total_buyers,
            "totalListings": total_listings,
            "liveListings": live,
            "soldListings": sold,
            "totalDeals": total_deals,
            "completedDeals": completed,
            "disputedDeals": disputed,
            "totalRevenue": float(revenue),
            "conversionRate": round(conversion, 2),
        })


class UsersGrowthView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(_users_growth(timezone.now()))


class ListingsGrowthView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(_listings_growth(timezone.now()))


class RevenueByMonthView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(_revenue_by_month(timezone.now()))


class DealsStatusView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        raw = dict(
            DealRoom.objects.values_list("status")
            .annotate(c=Count("id"))
            .values_list("status", "c")
        )
        for k in ["OPEN", "NEGOTIATING", "AGREED", "CANCELLED", "CLOSED"]:
            raw.setdefault(k, 0)

        return Response({
            "negotiating": raw.get("NEGOTIATING", 0),
            "accepted": raw.get("AGREED", 0),
            "reserved": 0,
            "completed": raw.get("CLOSED", 0),
            "disputed": 0,
            "cancelled": raw.get("CANCELLED", 0),
        })


class TopSellersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = (
            Listing.objects.values("seller__id", "seller__name")
            .annotate(views=Sum("views_count"), listings=Count("id"))
            .order_by("-views")[:5]
        )
        return Response([
            {
                "name": s["seller__name"] or "—",
                "views": s["views"] or 0,
                "listings": s["listings"],
            }
            for s in qs
        ])


class MostViewedListingsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = Listing.objects.order_by("-views_count")[:5]
        return Response([
            {
                "id": l.id,
                "title": l.title,
                "views": l.views_count,
                "price": float(l.price),
            }
            for l in qs
        ])


class TopCategoriesView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = (
            Listing.objects.values("category__slug", "category__name")
            .annotate(count=Count("id"), views=Sum("views_count"))
            .order_by("-views")[:5]
        )
        return Response([
            {
                "key": c["category__slug"] or "—",
                "name": c["category__name"] or "—",
                "count": c["count"],
                "views": c["views"] or 0,
            }
            for c in qs
        ])


class TopLocationsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = (
            Listing.objects.values("location")
            .annotate(count=Count("id"), views=Sum("views_count"))
            .order_by("-views")[:5]
        )
        return Response([
            {
                "name": l["location"] or "—",
                "count": l["count"],
                "views": l["views"] or 0,
            }
            for l in qs
        ])


class ConversionRateView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total = DealRoom.objects.count()
        completed = DealRoom.objects.filter(
            status=DealRoom.Status.CLOSED,
        ).count()
        rate = (completed / total * 100) if total else 0
        return Response({"conversionRate": round(rate, 2)})
