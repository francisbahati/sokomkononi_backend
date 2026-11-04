# apps/finance/views_reports.py
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO

from dateutil.relativedelta import relativedelta
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
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
def _visible_listings_qs():
    return Listing.objects.filter(is_deleted=False).exclude(
        status=Listing.Status.DRAFT,
    )


def _parse_date(s):
    """Parse YYYY-MM-DD → datetime (timezone-aware) au None."""
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
        return timezone.make_aware(
            datetime.combine(d, datetime.min.time()),
            timezone.get_current_timezone(),
        )
    except (ValueError, TypeError):
        return None


def _parse_end_date(s):
    """Parse YYYY-MM-DD → mwisho wa siku (23:59:59) timezone-aware."""
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
        return timezone.make_aware(
            datetime.combine(d, datetime.max.time()),
            timezone.get_current_timezone(),
        )
    except (ValueError, TypeError):
        return None


def _period_range(period, date_from=None, date_to=None):
    """
    Rudisha (start, end) kutoka period au custom date range.
    """
    # ✅ Tumia localtime ili upate muda wa Tanzania (EAT)
    now = timezone.localtime()

    if period == "custom":
        start = _parse_date(date_from)
        end = _parse_end_date(date_to) or now
        if not start:
            return None, None
        return start, end

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if period == "week":
        start = (now - timedelta(days=7))
        return start, now
    if period == "month":
        start = (now - relativedelta(months=1))
        return start, now
    if period == "year":
        start = (now - relativedelta(years=1))
        return start, now
    return None, None  # all


# ============================================================
# REVENUE-BY-RANGE HELPER (revenue halisi, sio GMV)
# ============================================================
def _revenue_in_range(start_dt, end_dt):
    """
    Hesabu revenue halisi kwa kipindi chochote (siku au mwezi) kutoka vyanzo vyote.
    ✅ Inatumia Coalesce("paid_at", "created_at")
    """
    from apps.banners.models import BannerAd
    from apps.boosting.models import ListingBoost
    from apps.bundles.models import BundlePurchase
    from apps.leading_fees.models import ListingLeading
    from apps.listings.models import ListingFee
    from apps.transactions.models import Reservation
    from .models import SuccessFeePayment

    total = Decimal("0.00")

    # Listing Fees
    qs = ListingFee.objects.filter(payment_status="PAID").annotate(
        effective_paid=Coalesce("paid_at", "created_at")
    )
    total += qs.filter(effective_paid__gte=start_dt, effective_paid__lt=end_dt).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

    # Boosts
    qs = ListingBoost.objects.filter(payment_status="PAID").annotate(
        effective_paid=Coalesce("paid_at", "created_at")
    )
    total += qs.filter(effective_paid__gte=start_dt, effective_paid__lt=end_dt).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

    # Leading
    qs = ListingLeading.objects.filter(payment_status=ListingLeading.PaymentStatus.PAID).annotate(
        effective_paid=Coalesce("paid_at", "created_at")
    )
    total += qs.filter(effective_paid__gte=start_dt, effective_paid__lt=end_dt).aggregate(s=Sum("price"))["s"] or Decimal("0.00")

    # Reservations
    qs = Reservation.objects.filter(payment_status="PAID").annotate(
        effective_paid=Coalesce("paid_at", "created_at")
    )
    total += qs.filter(effective_paid__gte=start_dt, effective_paid__lt=end_dt).aggregate(s=Sum("deposit_amount"))["s"] or Decimal("0.00")

    # Banner Ads
    qs = BannerAd.objects.filter(payment_status="PAID").annotate(
        effective_paid=Coalesce("paid_at", "created_at")
    )
    total += qs.filter(effective_paid__gte=start_dt, effective_paid__lt=end_dt).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

    # Bundle Purchases
    qs = BundlePurchase.objects.filter(status=BundlePurchase.Status.PAID).annotate(
        effective_paid=Coalesce("paid_at", "created_at")
    )
    total += qs.filter(effective_paid__gte=start_dt, effective_paid__lt=end_dt).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

    # Success Fees
    qs = SuccessFeePayment.objects.filter(payment_status="PAID").annotate(
        effective_paid=Coalesce("paid_at", "created_at")
    )
    total += qs.filter(effective_paid__gte=start_dt, effective_paid__lt=end_dt).aggregate(s=Sum("amount"))["s"] or Decimal("0.00")

    return total


# ============================================================
# REPORTS VIEW
# ============================================================
@method_decorator(csrf_exempt, name="dispatch")
class ReportsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        # ✅ Tumia localtime
        now = timezone.localtime()

        # ── CUSTOM DATE RANGE (optional) ────────────────────
        period = request.query_params.get("period", "all")
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        start, end = _period_range(period, date_from, date_to)

        # ── USER STATS ──────────────────────────────────────
        user_stats = calculate_user_stats()

        # Breakdown ya Watumiaji (Kwa ajili ya UI na Ripoti)
        users_breakdown = {
            "sellers": user_stats["sellersOnly"],
            "buyers": user_stats["buyersOnly"],
            "both": user_stats["bothRoles"],
            "neither": user_stats["neitherRole"],
            "admins": user_stats["totalAdmins"],
        }

        # ── USERS GROWTH ──────────────────────────────────
        start_day = (now - timedelta(days=29)).date()
        growth_rows = dict(
            User.objects
            .filter(
                is_deleted=False,
                date_joined__date__gte=start_day,
            )
            .annotate(d=TruncDate("date_joined"))
            .values_list("d")
            .annotate(c=Count("id"))
            .values_list("d", "c")
        )
        baseline = User.objects.filter(
            is_deleted=False,
            date_joined__date__lt=start_day,
        ).count()
        users_growth = []
        running = baseline
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).date()
            new_count = growth_rows.get(day, 0)
            running += new_count
            users_growth.append({
                "date": day.strftime("%Y-%m-%d"),
                "label": day.strftime("%d/%m"),
                "count": new_count,
                "cumulative": running,
            })

        # ── LISTINGS ────────────────────────────────────────
        visible_qs = _visible_listings_qs()

        if start and end:
            visible_qs_in_range = visible_qs.filter(
                created_at__gte=start, created_at__lte=end,
            )
        else:
            visible_qs_in_range = visible_qs

        total_listings = visible_qs_in_range.count()
        
        # Breakdown ya Mali kwa Status
        raw_listings_status = dict(
            visible_qs_in_range.values_list("status")
            .annotate(c=Count("id"))
            .values_list("status", "c")
        )
        listings_breakdown = {
            "live": raw_listings_status.get("LIVE", 0),
            "reserved": raw_listings_status.get("RESERVED", 0),
            "sold": raw_listings_status.get("SOLD", 0),
            "draft": raw_listings_status.get("DRAFT", 0),
            "pending_payment": raw_listings_status.get("PENDING_PAYMENT", 0),
            "approved_pending_payment": raw_listings_status.get("APPROVED_PENDING_PAYMENT", 0),
            "pending_approval": raw_listings_status.get("PENDING_APPROVAL", 0),
            "paid_pending_approval": raw_listings_status.get("PAID_PENDING_APPROVAL", 0),
            "in_review": raw_listings_status.get("IN_REVIEW", 0),
            "needs_edit": raw_listings_status.get("NEEDS_EDIT", 0),
            "rejected": raw_listings_status.get("REJECTED", 0),
            "paused": raw_listings_status.get("PAUSED", 0),
            "expired": raw_listings_status.get("EXPIRED", 0),
        }

        listings_growth = []
        for i in range(29, -1, -1):
            day = (now - timedelta(days=i)).date()
            count = visible_qs.filter(created_at__date=day).count()
            listings_growth.append({
                "date": day.strftime("%Y-%m-%d"),
                "label": day.strftime("%d/%m"),
                "count": count,
            })

        # ── DEALS ───────────────────────────────────────────
        deals_qs = DealRoom.objects.all()
        if start and end:
            deals_qs = deals_qs.filter(created_at__gte=start, created_at__lte=end)

        total_deals = deals_qs.count()
        
        raw_deals_status = dict(
            deals_qs.values_list("status")
            .annotate(c=Count("id"))
            .values_list("status", "c")
        )
        deals_breakdown = {
            "negotiating": raw_deals_status.get("NEGOTIATING", 0),
            "accepted": raw_deals_status.get("ACCEPTED", 0),
            "reserved": raw_deals_status.get("RESERVED", 0),
            "completed": raw_deals_status.get("COMPLETED", 0),
            "cancelled": raw_deals_status.get("CANCELLED", 0),
            "disputed": raw_deals_status.get("DISPUTED", 0),
            "awaiting_final_payment": raw_deals_status.get("AWAITING_FINAL_PAYMENT", 0),
            "payment_proof_submitted": raw_deals_status.get("PAYMENT_PROOF_SUBMITTED", 0),
        }

        # ── REVENUE ─────────────────────────────────────────
        try:
            from .services.revenue import calculate_financial_dashboard
            fees_data = calculate_financial_dashboard("all")
            revenue_by_stream = fees_data.get("by_type", {})
            total_revenue = float(fees_data.get("total_revenue", 0))
        except Exception:
            revenue_by_stream = {}
            total_revenue = 0.0

        # ✅ REVENUE BY MONTH
        revenue_by_month = []
        _anchor = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0,
        )
        for i in range(5, -1, -1):
            month_start = _anchor - relativedelta(months=i)
            month_end = month_start + relativedelta(months=1)
            month_total = _revenue_in_range(month_start, month_end)
            revenue_by_month.append({
                "label": month_start.strftime("%b"),
                "total": float(month_total),
            })

        # ✅ REVENUE BY DAY (Siku 7)
        revenue_by_day = []
        for i in range(6, -1, -1):
            day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            day_total = _revenue_in_range(day_start, day_end)
            revenue_by_day.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "label": day_start.strftime("%a"),
                "total": float(day_total),
            })

        # ── TOP SELLERS ─────────────────────────────────────
        top_sellers_qs = (
            visible_qs_in_range
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

        # ── MOST VIEWED ─────────────────────────────────────
        most_viewed_qs = visible_qs_in_range.order_by("-views_count")[:5]
        most_viewed = [
            {
                "id": l.id,
                "title": l.title,
                "views": l.views_count,
                "price": float(l.price),
            }
            for l in most_viewed_qs
        ]

        # ── TOP CATEGORIES ──────────────────────────────────
        cat_qs = (
            visible_qs_in_range
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

        # ── TOP LOCATIONS ───────────────────────────────────
        loc_qs = (
            visible_qs_in_range
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
            "period": period,
            "from": date_from,
            "to": date_to,
            
            # USERS
            "totalUsers": user_stats["totalUsers"],
            "usersBreakdown": users_breakdown,
            "usersGrowth": users_growth,

            # LISTINGS
            "totalListings": total_listings,
            "listingsBreakdown": listings_breakdown,
            "listingsGrowth": listings_growth,

            # DEALS
            "totalDeals": total_deals,
            "dealsBreakdown": deals_breakdown,

            # REVENUE
            "totalRevenue": total_revenue,
            "revenueByStream": revenue_by_stream,
            "revenueByMonth": revenue_by_month,
            "revenueByDay": revenue_by_day,

            # TOP LISTS
            "topSellers": top_sellers,
            "mostViewedListings": most_viewed,
            "topCategories": top_categories,
            "topLocations": top_locations,
        })


# ============================================================
# EXPORT REPORT — CSV / PDF / DOC
# ============================================================
@method_decorator(csrf_exempt, name="dispatch")
class ReportsExportView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        fmt = (request.query_params.get("format") or "csv").lower()
        period = (request.query_params.get("period") or "month").lower()
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")

        if fmt not in ("csv", "pdf", "doc"):
            return Response(
                {"detail": "Format si sahihi. Tumia csv, pdf, au doc."},
                status=400,
            )
        if period not in ("today", "week", "month", "year", "all", "custom"):
            return Response(
                {"detail": "Period si sahihi. Tumia today, week, month, year, all, au custom."},
                status=400,
            )
        if period == "custom" and (not date_from or not date_to):
            return Response(
                {"detail": "Custom period inahitaji 'from' na 'to' (YYYY-MM-DD)."},
                status=400,
            )

        data = ReportsView().get(request).data

        from .services.revenue import get_revenue_records
        period_map = {
            "today": "today",
            "week": "week",
            "month": "month",
            "year": "all",
            "all": "all",
            "custom": "all",
        }
        api_period = period_map.get(period, "all")

        try:
            records = get_revenue_records(period=api_period, source="all")
        except Exception:
            records = []

        if period == "custom":
            start = _parse_date(date_from)
            end = _parse_end_date(date_to)
            if start and end:
                filtered = []
                for r in records:
                    dt = r.get("paid_at") or r.get("created_at")
                    if dt and start <= dt <= end:
                        filtered.append(r)
                records = filtered

        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M")
        suffix = (
            f"{date_from or 'start'}_to_{date_to or 'end'}"
            if period == "custom"
            else period
        )

        if fmt == "csv":
            return self._csv(data, records, suffix, timestamp)
        if fmt == "pdf":
            return self._pdf(data, records, suffix, timestamp)
        return self._doc(data, records, suffix, timestamp)

    def _csv(self, data, records, period, timestamp):
        import csv
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="ripoti_{period}_{timestamp}.csv"'
        )
        response.write("\ufeff")
        writer = csv.writer(response)

        writer.writerow(["SokoMkononi — Ripoti ya Mfumo"])
        writer.writerow([f"Kipindi: {period}"])
        writer.writerow([f"Tarehe: {timezone.localtime().strftime('%Y-%m-%d %H:%M')}"])
        writer.writerow([])

        # WATUMIAJI
        ub = data.get("usersBreakdown", {})
        writer.writerow(["=== WATUMIAJI ==="])
        writer.writerow(["Jumla ya Watumiaji", data.get("totalUsers", 0)])
        writer.writerow(["Wauzaji Pekee", ub.get("sellers", 0)])
        writer.writerow(["Wanunuzi Pekee", ub.get("buyers", 0)])
        writer.writerow(["Wote Wawili", ub.get("both", 0)])
        writer.writerow(["Wapya (Neither)", ub.get("neither", 0)])
        writer.writerow(["Admins", ub.get("admins", 0)])
        writer.writerow([])

        # MALI
        lb = data.get("listingsBreakdown", {})
        status_labels = {
            "live": "Hai", "reserved": "Zimehifadhiwa", "sold": "Zimeuzwa",
            "draft": "Rasimu", "pending_payment": "Inasubiri Malipo",
            "approved_pending_payment": "Imeidhinishwa (Inasubiri Malipo)",
            "pending_approval": "Inasubiri Admin", "paid_pending_approval": "Imelipwa (Inasubiri Admin)",
            "in_review": "Inakaguliwa", "needs_edit": "Inahitaji Uhariri",
            "rejected": "Imekataliwa", "paused": "Imesimamishwa", "expired": "Imeisha Muda"
        }
        writer.writerow(["=== MALI ==="])
        writer.writerow(["Jumla ya Mali", data.get("totalListings", 0)])
        for status, count in lb.items():
            if count > 0:
                label = status_labels.get(status, status.replace("_", " ").title())
                writer.writerow([f"  - {label}", count])
        writer.writerow([])

        # DEALS
        db = data.get("dealsBreakdown", {})
        deal_labels = {
            "negotiating": "Inajadiliwa", "accepted": "Imekubaliwa",
            "reserved": "Imehifadhiwa", "completed": "Imekamilika",
            "cancelled": "Imeghairiwa", "disputed": "Mgogoro",
            "awaiting_final_payment": "Malipo ya Mwisho", "payment_proof_submitted": "Uthibitisho wa Malipo"
        }
        writer.writerow(["=== DEALS ==="])
        writer.writerow(["Jumla ya Deals", data.get("totalDeals", 0)])
        for status, count in db.items():
            if count > 0:
                label = deal_labels.get(status, status.replace("_", " ").title())
                writer.writerow([f"  - {label}", count])
        writer.writerow([])

        # MAPATO
        rev_streams = data.get("revenueByStream", {})
        stream_labels = {
            "listing": "Listing Fee", "reservation": "Reservation Fee",
            "boost": "Boost", "leading": "Leading", "advertise": "Advertisement",
            "success": "Success Fee", "bundle": "Bundle"
        }
        writer.writerow(["=== MAPATO ==="])
        writer.writerow(["Jumla ya Mapato", f"TZS {float(data.get('totalRevenue', 0)):,.0f}"])
        for key, amount in rev_streams.items():
            if amount > 0:
                label = stream_labels.get(key, key.replace("_", " ").title())
                writer.writerow([f"  - {label}", f"TZS {float(amount):,.0f}"])
        writer.writerow([])

        # ORODHA ZA JUU
        writer.writerow(["=== WAUZAJI BORA ==="])
        writer.writerow(["#", "Jina", "Mali", "Views"])
        for i, s in enumerate(data.get("topSellers", []), 1):
            writer.writerow([i, s.get("name"), s.get("listings", 0), s.get("views", 0)])
        writer.writerow([])

        writer.writerow(["=== MALI ZINAZOONEKANA ZAIDI ==="])
        writer.writerow(["#", "Jina", "Views", "Bei"])
        for i, l in enumerate(data.get("mostViewedListings", []), 1):
            writer.writerow([
                i, l.get("title"), l.get("views", 0),
                f"TZS {float(l.get('price', 0)):,.0f}",
            ])
        writer.writerow([])

        writer.writerow(["=== KATEGORIA ZINAZOONEKANA ZAIDI ==="])
        writer.writerow(["#", "Kategoria", "Mali", "Views"])
        for i, c in enumerate(data.get("topCategories", []), 1):
            writer.writerow([
                i, c.get("name") or c.get("key"), c.get("count", 0), c.get("views", 0),
            ])
        writer.writerow([])

        writer.writerow(["=== MAENEO YANAYOONEKANA ZAIDI ==="])
        writer.writerow(["#", "Eneo", "Mali", "Views"])
        for i, l in enumerate(data.get("topLocations", []), 1):
            writer.writerow([i, l.get("name"), l.get("count", 0), l.get("views", 0)])
        writer.writerow([])

        writer.writerow(["=== MIAMALA ILIYOKAMILIKA ==="])
        writer.writerow(["Tarehe", "Kumbukumbu", "Aina", "Kichwa", "Kiasi (TZS)", "Hali"])
        for r in records:
            date_val = r.get("paid_at") or r.get("created_at")
            date_str = date_val.strftime("%Y-%m-%d") if date_val else ""
            writer.writerow([
                date_str,
                str(r.get("payment_reference") or "—")[:20],
                r.get("source_label") or "—",
                (r.get("listing_title") or "")[:40],
                f"{float(r.get('amount', 0)):,.0f}",
                r.get("payment_status") or "—",
            ])

        return response

    def _pdf(self, data, records, period, timestamp):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
            )
        except ImportError:
            return Response(
                {"detail": "reportlab haipo. Wasiliana na admin."},
                status=500,
            )

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=1.5 * cm, leftMargin=1.5 * cm,
            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        )
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(
            "<b>SokoMkononi — Ripoti ya Mfumo</b>", styles["Title"],
        ))
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(Paragraph(
            f"Kipindi: <b>{period}</b> · Tarehe: {timezone.localtime().strftime('%Y-%m-%d %H:%M')}",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 0.5 * cm))

        def make_table(rows, headers):
            tbl_data = [headers] + rows
            t = Table(tbl_data, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#101A2E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E6E2D6")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F3EC")]),
            ]))
            return t

        # 1. WATUMIAJI
        elements.append(Paragraph("<b>1. Watumiaji</b>", styles["Heading2"]))
        ub = data.get("usersBreakdown", {})
        elements.append(make_table([
            ["Jumla ya Watumiaji", str(data.get("totalUsers", 0))],
            ["Wauzaji Pekee", str(ub.get("sellers", 0))],
            ["Wanunuzi Pekee", str(ub.get("buyers", 0))],
            ["Wote Wawili", str(ub.get("both", 0))],
            ["Wapya (Neither)", str(ub.get("neither", 0))],
            ["Admins", str(ub.get("admins", 0))],
        ], ["Kipimo", "Thamani"]))
        elements.append(Spacer(1, 0.5 * cm))

        # 2. MALI
        elements.append(Paragraph("<b>2. Mali kwa Hali</b>", styles["Heading2"]))
        lb = data.get("listingsBreakdown", {})
        status_labels = {
            "live": "Hai", "reserved": "Zimehifadhiwa", "sold": "Zimeuzwa",
            "draft": "Rasimu", "pending_payment": "Inasubiri Malipo",
            "approved_pending_payment": "Imeidhinishwa (Inasubiri Malipo)",
            "pending_approval": "Inasubiri Admin", "paid_pending_approval": "Imelipwa (Inasubiri Admin)",
            "in_review": "Inakaguliwa", "needs_edit": "Inahitaji Uhariri",
            "rejected": "Imekataliwa", "paused": "Imesimamishwa", "expired": "Imeisha Muda"
        }
        
        listing_rows = [["Jumla ya Mali", str(data.get("totalListings", 0))]]
        for status, count in lb.items():
            if count > 0:
                label = status_labels.get(status, status.replace("_", " ").title())
                listing_rows.append([f"  - {label}", str(count)])

        elements.append(make_table(listing_rows, ["Kipimo", "Thamani"]))
        elements.append(Spacer(1, 0.5 * cm))

        # 3. DEALS
        elements.append(Paragraph("<b>3. Deals kwa Hali</b>", styles["Heading2"]))
        db = data.get("dealsBreakdown", {})
        deal_labels = {
            "negotiating": "Inajadiliwa", "accepted": "Imekubaliwa",
            "reserved": "Imehifadhiwa", "completed": "Imekamilika",
            "cancelled": "Imeghairiwa", "disputed": "Mgogoro",
            "awaiting_final_payment": "Malipo ya Mwisho", "payment_proof_submitted": "Uthibitisho wa Malipo"
        }
        
        deals_rows = [["Jumla ya Deals", str(data.get("totalDeals", 0))]]
        for status, count in db.items():
            if count > 0:
                label = deal_labels.get(status, status.replace("_", " ").title())
                deals_rows.append([f"  - {label}", str(count)])

        elements.append(make_table(deals_rows, ["Kipimo", "Thamani"]))
        elements.append(Spacer(1, 0.5 * cm))

        # 4. MAPATO
        elements.append(Paragraph("<b>4. Mapato kwa Njia</b>", styles["Heading2"]))
        rev_streams = data.get("revenueByStream", {})
        stream_labels = {
            "listing": "Listing Fee", "reservation": "Reservation Fee",
            "boost": "Boost", "leading": "Leading", "advertise": "Advertisement",
            "success": "Success Fee", "bundle": "Bundle"
        }
        
        rev_rows = [["Jumla ya Mapato", f"TZS {float(data.get('totalRevenue', 0)):,.0f}"]]
        for key, amount in rev_streams.items():
            if amount > 0:
                label = stream_labels.get(key, key.replace("_", " ").title())
                rev_rows.append([f"  - {label}", f"TZS {float(amount):,.0f}"])

        elements.append(make_table(rev_rows, ["Kipimo", "Thamani"]))

        doc.build(elements)
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="ripoti_{period}_{timestamp}.pdf"'
        )
        return response

    def _doc(self, data, records, period, timestamp):
        try:
            from docx import Document
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            return Response(
                {"detail": "python-docx haipo. Wasiliana na admin."},
                status=500,
            )

        doc = Document()
        h = doc.add_heading("SokoMkononi — Ripoti ya Mfumo", 0)
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER

        sub = doc.add_paragraph(
            f"Kipimo: {period} · Tarehe: {timezone.localtime().strftime('%Y-%m-%d %H:%M')}"
        )
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

        def add_section(title, rows, headers):
            doc.add_heading(title, level=1)
            t = doc.add_table(rows=1, cols=len(headers))
            t.style = "Light Grid Accent 1"
            hdr = t.rows[0].cells
            for i, h in enumerate(headers):
                hdr[i].text = h
            for r in rows:
                cells = t.add_row().cells
                for i, v in enumerate(r):
                    cells[i].text = str(v)

        # 1. WATUMIAJI
        ub = data.get("usersBreakdown", {})
        add_section("1. Watumiaji", [
            ["Jumla ya Watumiaji", data.get("totalUsers", 0)],
            ["Wauzaji Pekee", ub.get("sellers", 0)],
            ["Wanunuzi Pekee", ub.get("buyers", 0)],
            ["Wote Wawili", ub.get("both", 0)],
            ["Wapya (Neither)", ub.get("neither", 0)],
            ["Admins", ub.get("admins", 0)],
        ], ["Kipimo", "Thamani"])

        # 2. MALI
        lb = data.get("listingsBreakdown", {})
        status_labels = {
            "live": "Hai", "reserved": "Zimehifadhiwa", "sold": "Zimeuzwa",
            "draft": "Rasimu", "pending_payment": "Inasubiri Malipo",
            "approved_pending_payment": "Imeidhinishwa (Inasubiri Malipo)",
            "pending_approval": "Inasubiri Admin", "paid_pending_approval": "Imelipwa (Inasubiri Admin)",
            "in_review": "Inakaguliwa", "needs_edit": "Inahitaji Uhariri",
            "rejected": "Imekataliwa", "paused": "Imesimamishwa", "expired": "Imeisha Muda"
        }
        listing_rows = [["Jumla ya Mali", data.get("totalListings", 0)]]
        for status, count in lb.items():
            if count > 0:
                label = status_labels.get(status, status.replace("_", " ").title())
                listing_rows.append([f"  - {label}", count])
        add_section("2. Mali kwa Hali", listing_rows, ["Kipimo", "Thamani"])

        # 3. DEALS
        db = data.get("dealsBreakdown", {})
        deal_labels = {
            "negotiating": "Inajadiliwa", "accepted": "Imekubaliwa",
            "reserved": "Imehifadhiwa", "completed": "Imekamilika",
            "cancelled": "Imeghairiwa", "disputed": "Mgogoro",
            "awaiting_final_payment": "Malipo ya Mwisho", "payment_proof_submitted": "Uthibitisho wa Malipo"
        }
        deals_rows = [["Jumla ya Deals", data.get("totalDeals", 0)]]
        for status, count in db.items():
            if count > 0:
                label = deal_labels.get(status, status.replace("_", " ").title())
                deals_rows.append([f"  - {label}", count])
        add_section("3. Deals kwa Hali", deals_rows, ["Kipimo", "Thamani"])

        # 4. MAPATO
        rev_streams = data.get("revenueByStream", {})
        stream_labels = {
            "listing": "Listing Fee", "reservation": "Reservation Fee",
            "boost": "Boost", "leading": "Leading", "advertise": "Advertisement",
            "success": "Success Fee", "bundle": "Bundle"
        }
        rev_rows = [["Jumla ya Mapato", f"TZS {float(data.get('totalRevenue', 0)):,.0f}"]]
        for key, amount in rev_streams.items():
            if amount > 0:
                label = stream_labels.get(key, key.replace("_", " ").title())
                rev_rows.append([f"  - {label}", f"TZS {float(amount):,.0f}"])
        add_section("4. Mapato kwa Njia", rev_rows, ["Kipimo", "Thamani"])

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            buffer.read(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="ripoti_{period}_{timestamp}.docx"'
        )
        return response