# apps/finance/views_success_fee.py
"""
Success Fee views:
- POST /api/finance/success-fee/           — FimiPay order (existing)
- GET  /api/finance/success-fee/status/    — Check if download is free/paid
- GET  /api/finance/success-fee/download/  — Download transactions (PDF/CSV/DOC)

SASISHO:
  - Inapokea `period` param: today | week | two_weeks | month | year | all
  - _get_user_transactions() sasa inachukua pia:
    • Transaction (buyer + seller) — sale, purchase
    • SuccessFeePayment
    • BundlePurchase
    • ✅ BannerAd (advertising)
  - ✅ Inarudisha COMPLETED/PAID pekee (pending/failed hazionekani)
"""
import csv
from datetime import timedelta
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.listings.models import ListingFee
from apps.boosting.models import ListingBoost
from apps.transactions.models import Reservation, Transaction
from apps.bundles.models import BundlePurchase
from apps.banners.models import BannerAd   # ⬅️ ONGEZA HII

from .models import SuccessFeeConfig, SuccessFeePayment
from .services_success_fee import (
    DEFAULT_PURPOSE,
    compute_download_fee,
    create_success_fee_payment,
    has_valid_success_fee_payment,
    initiate_success_fee_payment,
)


# ============================================================
# PERIOD RANGE
# ============================================================
PERIOD_DAYS = {
    "today": 0,
    "week": 7,
    "two_weeks": 14,
    "month": 30,
    "year": 365,
    "all": None,
}


def get_period_start(period):
    period = (period or "all").lower().strip()
    if period not in PERIOD_DAYS:
        period = "all"

    days = PERIOD_DAYS[period]
    if days is None:
        return None

    now = timezone.now()
    if days == 0:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    return now - timedelta(days=days)


# ============================================================
# HELPERS
# ============================================================
def _get_success_fee_config():
    obj, _ = SuccessFeeConfig.objects.get_or_create(
        key="default",
        defaults={
            "label_sw": "Ada ya Mafanikio",
            "label_en": "Success Fee",
            "desc_sw": "Ada ndogo ya kupakua ripoti ya miamala.",
            "desc_en": "Small fee to download transactions report.",
            "percentage": 2.0,
            "min_fee": 5000,
            "max_fee": 500000,
            "is_enabled": True,
        },
    )
    return obj


def _is_sw():
    return True


def _get_user_transactions(user, period="all"):
    """
    Chukua miamala ILIYOKAMILIKA (completed/paid) pekee:
    - ListingFee (seller) — payment_status = PAID
    - ListingBoost (seller) — payment_status = PAID
    - Reservation (buyer) — payment_status = PAID
    - Transaction (buyer + seller) — status = COMPLETED
    - SuccessFeePayment — payment_status = PAID
    - BundlePurchase — status = PAID
    - BannerAd (advertising) — payment_status = PAID
    """
    records = []
    start = get_period_start(period)

    # ── Listing Fees (PAID pekee) ──
    qs = (
        ListingFee.objects
        .filter(seller=user, payment_status="PAID")
        .select_related("listing")
        .order_by("-created_at")
    )
    if start:
        qs = qs.filter(created_at__gte=start)
    for item in qs:
        records.append({
            "date": item.paid_at or item.created_at,
            "ref": item.payment_reference or f"LF-{item.pk}",
            "type": "Ada ya Kuchapisha" if _is_sw() else "Listing Fee",
            "title": item.listing.title if item.listing else "—",
            "amount": float(item.amount or 0),
            "status": "Completed",
            "paid_at": item.paid_at,
        })

    # ── Boosts (PAID pekee) ──
    qs = (
        ListingBoost.objects
        .filter(seller=user, payment_status="PAID")
        .select_related("listing", "package")
        .order_by("-created_at")
    )
    if start:
        qs = qs.filter(created_at__gte=start)
    for item in qs:
        records.append({
            "date": item.paid_at or item.created_at,
            "ref": item.payment_reference or f"B-{item.pk}",
            "type": "Ada ya Kukuza" if _is_sw() else "Boost Fee",
            "title": item.listing.title if item.listing else "—",
            "amount": float(item.amount or 0),
            "status": "Completed",
            "paid_at": item.paid_at,
        })

    # ── Reservations (buyer, PAID pekee) ──
    qs = (
        Reservation.objects
        .filter(transaction__buyer=user, payment_status="PAID")
        .select_related("transaction", "transaction__listing")
        .order_by("-created_at")
    )
    if start:
        qs = qs.filter(created_at__gte=start)
    for item in qs:
        listing = item.transaction.listing if item.transaction else None
        records.append({
            "date": item.paid_at or item.created_at,
            "ref": item.payment_reference or f"R-{item.pk}",
            "type": "Ada ya Uhifadhi" if _is_sw() else "Reservation Fee",
            "title": listing.title if listing else "—",
            "amount": float(item.deposit_amount or 0),
            "status": "Completed",
            "paid_at": item.paid_at,
        })

    # ── Transactions (buyer) — Purchase (COMPLETED pekee) ──
    qs = (
        Transaction.objects
        .filter(buyer=user, status=Transaction.Status.COMPLETED)
        .select_related("listing", "seller")
        .order_by("-completed_at", "-created_at")
    )
    if start:
        qs = qs.filter(completed_at__gte=start)
    for item in qs:
        records.append({
            "date": item.completed_at or item.created_at,
            "ref": f"TXN-{item.pk}",
            "type": "Ununuzi" if _is_sw() else "Purchase",
            "title": item.listing.title if item.listing else "—",
            "amount": float(item.agreed_price or 0),
            "status": "Completed",
            "paid_at": item.completed_at,
        })

    # ── Transactions (seller) — Sale (COMPLETED pekee) ──
    qs = (
        Transaction.objects
        .filter(seller=user, status=Transaction.Status.COMPLETED)
        .select_related("listing", "buyer")
        .order_by("-completed_at", "-created_at")
    )
    if start:
        qs = qs.filter(completed_at__gte=start)
    for item in qs:
        records.append({
            "date": item.completed_at or item.created_at,
            "ref": f"TXN-{item.pk}",
            "type": "Mauzo" if _is_sw() else "Sale",
            "title": item.listing.title if item.listing else "—",
            "amount": float(item.agreed_price or 0),
            "status": "Completed",
            "paid_at": item.completed_at,
        })

    # ── Success Fee Payments (PAID pekee) ──
    qs = (
        SuccessFeePayment.objects
        .filter(
            user=user,
            payment_status=SuccessFeePayment.PaymentStatus.PAID,
        )
        .order_by("-created_at")
    )
    if start:
        qs = qs.filter(created_at__gte=start)
    for item in qs:
        records.append({
            "date": item.paid_at or item.created_at,
            "ref": item.payment_reference or f"SFE-{item.pk}",
            "type": "Ada ya Mafanikio" if _is_sw() else "Success Fee",
            "title": item.purpose or "Download report",
            "amount": float(item.amount or 0),
            "status": "Completed",
            "paid_at": item.paid_at,
        })

    # ── Bundle Purchases (PAID pekee) ──
    qs = (
        BundlePurchase.objects
        .filter(user=user, status=BundlePurchase.Status.PAID)
        .select_related("bundle")
        .order_by("-created_at")
    )
    if start:
        qs = qs.filter(created_at__gte=start)
    for item in qs:
        bundle_code = (
            getattr(item.bundle, "code", "Bundle") if item.bundle else "Bundle"
        )
        records.append({
            "date": item.paid_at or item.created_at,
            "ref": item.payment_reference or f"BP-{item.pk}",
            "type": "Vifurushi" if _is_sw() else "Bundle",
            "title": bundle_code,
            "amount": float(item.amount or 0),
            "status": "Completed",
            "paid_at": item.paid_at,
        })

    # ── Banner Ads / Advertising (PAID pekee) ──
    qs = (
        BannerAd.objects
        .filter(seller=user, payment_status="PAID")
        .select_related("listing")
        .order_by("-created_at")
    )
    if start:
        qs = qs.filter(created_at__gte=start)
    for item in qs:
        # BannerAd inaweza kuwa na `listing_title` field au `listing.title`
        title = (
            getattr(item, "listing_title", "")
            or (item.listing.title if item.listing else "")
            or "—"
        )
        records.append({
            "date": item.paid_at or item.created_at,
            "ref": item.payment_reference or f"AD-{item.pk}",
            "type": "Matangazo" if _is_sw() else "Ads",
            "title": title,
            "amount": float(item.amount or 0),
            "status": "Completed",
            "paid_at": item.paid_at,
        })

    records.sort(key=lambda r: r["date"], reverse=True)
    return records


# ============================================================
# EXISTING — FimiPay order
# ============================================================
class SuccessFeeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        config = _get_success_fee_config()

        if not config.is_enabled:
            return Response(
                {"detail": "Ada ya mafanikio imezimwa. Hakuna malipo yanayohitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        purpose = (request.data.get("purpose") or DEFAULT_PURPOSE)
        purpose = str(purpose).strip() or DEFAULT_PURPOSE

        payment = create_success_fee_payment(
            user=request.user,
            purpose=purpose,
            amount=compute_download_fee(config),
        )
        data = initiate_success_fee_payment(
            payment=payment,
            user=request.user,
            payment_method=request.data.get("payment_method", "mobile"),
            phone=request.data.get("phone", ""),
        )
        return Response({"fimipay": data}, status=status.HTTP_201_CREATED)


# ============================================================
# Status
# ============================================================
class SuccessFeeStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        config = _get_success_fee_config()
        is_free = not config.is_enabled
        return Response({
            "is_free": is_free,
            "fee": str(config.min_fee),
            "requires_payment": config.is_enabled,
            "success_fee_enabled": config.is_enabled,
            "percentage": str(config.percentage),
            "max_fee": str(config.max_fee),
            "formats": ["pdf", "csv", "doc"],
            "periods": list(PERIOD_DAYS.keys()),
        })


# ============================================================
# Download — pamoja na period
# ============================================================
class SuccessFeeDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        fmt = (request.query_params.get("format") or "pdf").lower()
        if fmt not in ("pdf", "csv", "doc"):
            return Response(
                {"detail": "Format si sahihi. Tumia pdf, csv, au doc."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period = (request.query_params.get("period") or "all").lower()
        if period not in PERIOD_DAYS:
            period = "all"

        config = _get_success_fee_config()

        if config.is_enabled and not has_valid_success_fee_payment(request.user):
            return Response(
                {
                    "requires_payment": True,
                    "fee": str(config.min_fee),
                    "message": "Lipa ada ya mafanikio kwanza ili kupakua.",
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        records = _get_user_transactions(request.user, period=period)
        if not records:
            return Response(status=status.HTTP_204_NO_CONTENT)

        timestamp = timezone.now().strftime("%Y%m%d")

        if fmt == "csv":
            return self._generate_csv(records, timestamp, period)
        if fmt == "pdf":
            return self._generate_pdf(records, timestamp, period)
        return self._generate_doc(records, timestamp, period)

    # ── CSV ──
    def _generate_csv(self, records, timestamp, period):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="miamala_{period}_{timestamp}.csv"'
        )
        response.write("\ufeff")

        writer = csv.writer(response)
        writer.writerow([
            "Tarehe", "Kumbukumbu", "Aina", "Kichwa",
            "Kiasi (TZS)", "Hali", "Ilipwa",
        ])
        for r in records:
            writer.writerow([
                r["date"].strftime("%Y-%m-%d") if r["date"] else "",
                r["ref"],
                r["type"],
                r["title"],
                f"{r['amount']:.2f}",
                r["status"],
                r["paid_at"].strftime("%Y-%m-%d %H:%M") if r["paid_at"] else "",
            ])
        return response

    # ── PDF ──
    def _generate_pdf(self, records, timestamp, period):
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
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        styles = getSampleStyleSheet()
        elements = []

        title = Paragraph(
            "<b>SokoMkononi — Miamala Yangu</b>",
            styles["Title"],
        )
        elements.append(title)
        elements.append(Spacer(1, 0.3 * cm))

        period_label = {
            "today": "Leo",
            "week": "Wiki Hii",
            "two_weeks": "Wiki Mbili",
            "month": "Mwezi Huu",
            "year": "Mwaka Huu",
            "all": "Zote",
        }.get(period, "Zote")

        subtitle = Paragraph(
            f"Ripoti ya miamala iliyokamilika · Kipindi: {period_label} · {len(records)} rekodi",
            styles["Normal"],
        )
        elements.append(subtitle)
        elements.append(Spacer(1, 0.5 * cm))

        header = [
            "Tarehe", "Kumbukumbu", "Aina", "Kichwa",
            "Kiasi (TZS)", "Hali",
        ]
        data = [header]
        for r in records:
            data.append([
                r["date"].strftime("%Y-%m-%d") if r["date"] else "",
                r["ref"][:20],
                r["type"][:20],
                (r["title"] or "")[:30],
                f"{r['amount']:,.0f}",
                r["status"],
            ])

        table = Table(data, colWidths=[
            2.2 * cm, 3.0 * cm, 3.0 * cm, 4.5 * cm, 2.5 * cm, 2.0 * cm,
        ])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#101A2E")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (4, 1), (4, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E6E2D6")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F3EC")]),
        ]))
        elements.append(table)

        doc.build(elements)
        buffer.seek(0)

        response = HttpResponse(
            buffer.read(),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="miamala_{period}_{timestamp}.pdf"'
        )
        return response

    # ── DOC ──
    def _generate_doc(self, records, timestamp, period):
        try:
            from docx import Document
            from docx.enum.table import WD_TABLE_ALIGNMENT
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.shared import Pt
        except ImportError:
            return Response(
                {"detail": "python-docx haipo. Wasiliana na admin."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        doc = Document()

        heading = doc.add_heading("SokoMkononi — Miamala Yangu", 0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

        period_label = {
            "today": "Leo",
            "week": "Wiki Hii",
            "two_weeks": "Wiki Mbili",
            "month": "Mwezi Huu",
            "year": "Mwaka Huu",
            "all": "Zote",
        }.get(period, "Zote")

        subtitle = doc.add_paragraph(
            f"Ripoti ya miamala iliyokamilika · Kipindi: {period_label} · {len(records)} rekodi"
        )
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()

        table = doc.add_table(rows=1, cols=6)
        table.style = "Light Grid Accent 1"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        hdr_cells = table.rows[0].cells
        headers = ["Tarehe", "Kumbukumbu", "Aina", "Kichwa", "Kiasi (TZS)", "Hali"]
        for i, h in enumerate(headers):
            hdr_cells[i].text = h
            for paragraph in hdr_cells[i].paragraphs:
                for run in paragraph.runs:
                    run.bold = True
                    run.font.size = Pt(9)

        for r in records:
            row = table.add_row().cells
            row[0].text = r["date"].strftime("%Y-%m-%d") if r["date"] else ""
            row[1].text = r["ref"][:25]
            row[2].text = r["type"]
            row[3].text = r["title"] or ""
            row[4].text = f"{r['amount']:,.0f}"
            row[5].text = r["status"]
            for cell in row:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(8)

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.read(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        )
        response["Content-Disposition"] = (
            f'attachment; filename="miamala_{period}_{timestamp}.docx"'
        )
        return response