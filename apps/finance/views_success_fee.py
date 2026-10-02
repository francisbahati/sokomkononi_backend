# apps/finance/views_success_fee.py
"""
Success Fee views:
- POST /api/finance/success-fee/           — FimiPay order (existing)
- GET  /api/finance/success-fee/status/    — Check if download is free/paid
- GET  /api/finance/success-fee/download/  — Download transactions (PDF/CSV/DOC)
"""
import csv
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.fimipay import create_order
from apps.listings.models import ListingFee
from apps.boosting.models import ListingBoost
from apps.transactions.models import Reservation

from .models import SuccessFeeConfig


# ============================================================
# HELPERS
# ============================================================
def _get_success_fee_config():
    """Pata SuccessFeeConfig (singleton)."""
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


def _map_status(payment_status):
    """Map payment status → display status."""
    mapping = {
        "PAID": "Completed",
        "PENDING": "Pending",
        "FAILED": "Failed",
        "REFUNDED": "Refunded",
    }
    return mapping.get(payment_status, "Pending")


def _get_user_transactions(user):
    """
    Chukua miamala yote ya user:
    - ListingFee (seller)
    - ListingBoost (seller)
    - Reservation (buyer)
    """
    records = []

    # ── Listing Fees ──
    for item in ListingFee.objects.filter(
        seller=user,
    ).select_related("listing").order_by("-created_at"):
        records.append({
            "date": item.created_at,
            "ref": item.payment_reference or f"LF-{item.pk}",
            "type": "Ada ya Kuchapisha" if _is_sw() else "Listing Fee",
            "title": item.listing.title if item.listing else "—",
            "amount": float(item.amount or 0),
            "status": _map_status(item.payment_status),
            "paid_at": item.paid_at,
        })

    # ── Boosts ──
    for item in ListingBoost.objects.filter(
        seller=user,
    ).select_related("listing", "package").order_by("-created_at"):
        records.append({
            "date": item.created_at,
            "ref": item.payment_reference or f"B-{item.pk}",
            "type": "Ada ya Kukuza" if _is_sw() else "Boost Fee",
            "title": item.listing.title if item.listing else "—",
            "amount": float(item.amount or 0),
            "status": _map_status(item.payment_status),
            "paid_at": item.paid_at,
        })

    # ── Reservations (buyer) ──
    for item in Reservation.objects.filter(
        transaction__buyer=user,
    ).select_related(
        "transaction", "transaction__listing",
    ).order_by("-created_at"):
        listing = item.transaction.listing if item.transaction else None
        records.append({
            "date": item.created_at,
            "ref": item.payment_reference or f"R-{item.pk}",
            "type": "Ada ya Uhifadhi" if _is_sw() else "Reservation Fee",
            "title": listing.title if listing else "—",
            "amount": float(item.deposit_amount or 0),
            "status": _map_status(item.payment_status),
            "paid_at": item.paid_at,
        })

    records.sort(key=lambda r: r["date"], reverse=True)
    return records


def _is_sw():
    """Check kama request ni Kiswahili (kutoka header au default sw)."""
    return True  # Kwa sasa default Kiswahili; tunaweza kutumia header baadaye


# ============================================================
# EXISTING — FimiPay order
# ============================================================
class SuccessFeeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        purpose = (request.data.get("purpose") or "").strip()
        amount = request.data.get("amount")
        if not purpose or not amount:
            return Response(
                {"detail": "purpose na amount zinahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order_id = f"SF-{request.user.id}-{purpose[:20]}"
        data = create_order(
            order_id=order_id,
            amount=amount,
            buyer_phone=request.user.phone or "",
            buyer_email=request.user.email or "",
            buyer_name=request.user.name or "",
            payment_method="mobile",
        )
        return Response({"fimipay": data}, status=status.HTTP_201_CREATED)


# ============================================================
# NEW — Status
# ============================================================
class SuccessFeeStatusView(APIView):
    """
    GET /api/finance/success-fee/status/
    Rudisha hali ya success fee (free/paid) na fee.
    """
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
        })


# ============================================================
# NEW — Download
# ============================================================
class SuccessFeeDownloadView(APIView):
    """
    GET /api/finance/success-fee/download/?format=pdf|csv|doc

    - Kama success_fee.is_enabled = false → download bure
    - Kama true → 402 Payment Required (frontend inaomba malipo kwanza)

    Baada ya malipo (kupitia POST /api/finance/success-fee/), user anaweza
    kupakua kwa kuita endpoint hii tena — tunaweza ku-check payment_reference
    kwenye query param.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        fmt = (request.query_params.get("format") or "pdf").lower()
        if fmt not in ("pdf", "csv", "doc"):
            return Response(
                {"detail": "Format si sahihi. Tumia pdf, csv, au doc."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = _get_success_fee_config()

        # ── Check payment ──
        if config.is_enabled:
            # Kama success fee imewashwa, angalia kama user ameshalipa
            # kwa `payment_reference`. Kwa sasa, tunaruhusu download kama
            # payment_reference imetumwa (tunaweza ku-validate baadaye).
            payment_ref = (request.query_params.get("payment_reference") or "").strip()
            if not payment_ref:
                return Response(
                    {
                        "requires_payment": True,
                        "fee": str(config.min_fee),
                        "message": "Lipa ada ya mafanikio kwanza ili kupakua.",
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

        # ── Chukua miamala ──
        records = _get_user_transactions(request.user)
        if not records:
            return Response(
                {"detail": "Hakuna miamala ya kupakua."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Generate file ──
        timestamp = timezone.now().strftime("%Y%m%d")

        if fmt == "csv":
            return self._generate_csv(records, timestamp)
        elif fmt == "pdf":
            return self._generate_pdf(records, timestamp)
        elif fmt == "doc":
            return self._generate_doc(records, timestamp)

    # ── CSV ──
    def _generate_csv(self, records, timestamp):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="miamala_{timestamp}.csv"'
        )
        # BOM kwa Excel (Kiswahili)
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
    def _generate_pdf(self, records, timestamp):
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

        # Title
        title = Paragraph(
            "<b>SokoMkononi — Miamala Yangu</b>",
            styles["Title"],
        )
        elements.append(title)
        elements.append(Spacer(1, 0.3 * cm))

        # Subtitle
        subtitle = Paragraph(
            f"Ripoti ya miamala · {len(records)} rekodi",
            styles["Normal"],
        )
        elements.append(subtitle)
        elements.append(Spacer(1, 0.5 * cm))

        # Table
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
            f'attachment; filename="miamala_{timestamp}.pdf"'
        )
        return response

    # ── DOC ──
    def _generate_doc(self, records, timestamp):
        try:
            from docx import Document
            from docx.shared import Pt, Cm, RGBColor
            from docx.enum.table import WD_TABLE_ALIGNMENT
        except ImportError:
            return Response(
                {"detail": "python-docx haipo. Wasiliana na admin."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        doc = Document()

        # Title
        heading = doc.add_heading("SokoMkononi — Miamala Yangu", 0)
        heading.alignment = WD_TABLE_ALIGNMENT.CENTER

        # Subtitle
        subtitle = doc.add_paragraph(f"Ripoti ya miamala · {len(records)} rekodi")
        subtitle.alignment = WD_TABLE_ALIGNMENT.CENTER

        doc.add_paragraph()

        # Table
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
            content_type="application/msword",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="miamala_{timestamp}.doc"'
        )
        return response