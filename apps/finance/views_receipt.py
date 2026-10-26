# apps/finance/views_receipt.py
"""
Receipt download — PDF ya muamala mmoja.

GET /api/finance/transactions/<int:pk>/receipt/

Inatafuta muamala kwenye vyanzo vyote:
  - ListingFee
  - ListingBoost
  - Reservation
  - Transaction (buyer + seller)
  - SuccessFeePayment
  - BundlePurchase

✅ Inarudisha receipt ya COMPLETED/PAID pekee.
   Muamala ambao haujakamilika haupatikani (404).

Ulinzi: user anaweza kuona receipt ya muamala wake pekee.
"""
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
from apps.payments.services.status_sync import sync_user_pending

from .models import SuccessFeePayment


# ============================================================
# STATUS MAPPING
# ============================================================
def _map_status(raw):
    mapping = {
        "PAID": "Imelipwa",
        "PENDING": "Inasubiri",
        "FAILED": "Imeshindikana",
        "REFUNDED": "Imerejeshwa",
        "COMPLETED": "Imekamilika",
        "CANCELLED": "Imeghairiwa",
        "RESERVATION_PENDING": "Inasubiri Uhifadhi",
        "RESERVED": "Imehifadhiwa",
        "INSPECTION": "Ukaguzi",
        "READY_FOR_FINAL_PAYMENT": "Tayari kwa Malipo ya Mwisho",
        "DISPUTED": "Ina Mgogoro",
    }
    return mapping.get(str(raw).upper(), str(raw))


# ============================================================
# FIND TRANSACTION
# ============================================================
def _find_transaction(pk, user):
    """Tafuta muamala COMPLETED/PAID pekee."""
    # ── 1. ListingFee ──
    try:
        obj = (
            ListingFee.objects
            .select_related("listing")
            .get(pk=pk, seller=user, payment_status="PAID")
        )
        return {
            "kind": "listing_fee",
            "ref": obj.payment_reference or f"LF-{obj.pk}",
            "type_sw": "Ada ya Kuchapisha",
            "type_en": "Listing Fee",
            "title": obj.listing.title if obj.listing else "—",
            "amount": obj.amount,
            "status": obj.payment_status,
            "date": obj.created_at,
            "paid_at": obj.paid_at,
            "method": getattr(obj, "payment_method", None),
            "phone": getattr(obj, "phone", None),
        }
    except ListingFee.DoesNotExist:
        pass

    # ── 2. ListingBoost ──
    try:
        obj = (
            ListingBoost.objects
            .select_related("listing", "package")
            .get(pk=pk, seller=user, payment_status="PAID")
        )
        return {
            "kind": "boost",
            "ref": obj.payment_reference or f"B-{obj.pk}",
            "type_sw": "Ada ya Kukuza",
            "type_en": "Boost Fee",
            "title": obj.listing.title if obj.listing else "—",
            "amount": obj.amount,
            "status": obj.payment_status,
            "date": obj.created_at,
            "paid_at": obj.paid_at,
            "method": getattr(obj, "payment_method", None),
            "phone": getattr(obj, "phone", None),
        }
    except ListingBoost.DoesNotExist:
        pass

    # ── 3. Reservation ──
    try:
        obj = (
            Reservation.objects
            .select_related("transaction", "transaction__listing")
            .get(pk=pk, transaction__buyer=user, payment_status="PAID")
        )
        listing = obj.transaction.listing if obj.transaction else None
        return {
            "kind": "reservation",
            "ref": obj.payment_reference or f"R-{obj.pk}",
            "type_sw": "Ada ya Uhifadhi",
            "type_en": "Reservation Fee",
            "title": listing.title if listing else "—",
            "amount": obj.deposit_amount,
            "status": obj.payment_status,
            "date": obj.created_at,
            "paid_at": obj.paid_at,
            "method": getattr(obj, "payment_method", None),
            "phone": getattr(obj, "phone", None),
        }
    except Reservation.DoesNotExist:
        pass

    # ── 4. Transaction ──
    try:
        obj = (
            Transaction.objects
            .select_related("listing", "buyer", "seller")
            .get(pk=pk, status=Transaction.Status.COMPLETED)
        )
        if user.id not in [obj.buyer_id, obj.seller_id]:
            raise Transaction.DoesNotExist

        is_seller = user.id == obj.seller_id
        return {
            "kind": "transaction",
            "ref": f"TXN-{obj.pk}",
            "type_sw": "Mauzo" if is_seller else "Ununuzi",
            "type_en": "Sale" if is_seller else "Purchase",
            "title": obj.listing.title if obj.listing else "—",
            "amount": obj.agreed_price,
            "status": obj.status,
            "date": obj.created_at,
            "paid_at": obj.completed_at,
            "method": None,
            "phone": None,
        }
    except Transaction.DoesNotExist:
        pass

    # ── 5. SuccessFeePayment ──
    try:
        obj = SuccessFeePayment.objects.get(
            pk=pk,
            user=user,
            payment_status=SuccessFeePayment.PaymentStatus.PAID,
        )
        return {
            "kind": "success_fee",
            "ref": obj.payment_reference or f"SFE-{obj.pk}",
            "type_sw": "Ada ya Mafanikio",
            "type_en": "Success Fee",
            "title": obj.purpose or "Download report",
            "amount": obj.amount,
            "status": obj.payment_status,
            "date": obj.created_at,
            "paid_at": obj.paid_at,
            "method": None,
            "phone": None,
        }
    except SuccessFeePayment.DoesNotExist:
        pass

    # ── 6. BundlePurchase ──
    try:
        obj = (
            BundlePurchase.objects
            .select_related("bundle")
            .get(pk=pk, user=user, status=BundlePurchase.Status.PAID)
        )
        return {
            "kind": "bundle",
            "ref": obj.payment_reference or f"BP-{obj.pk}",
            "type_sw": "Kifurushi",
            "type_en": "Bundle",
            "title": obj.bundle.code if obj.bundle else "Bundle",
            "amount": obj.amount,
            "status": obj.status,
            "date": obj.created_at,
            "paid_at": obj.paid_at,
            "method": None,
            "phone": None,
        }
    except BundlePurchase.DoesNotExist:
        pass

    return None


# ============================================================
# RECEIPT VIEW
# ============================================================
class TransactionReceiptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        # ⬇️ SYNC kabla ya receipt (manual: sync zote PENDING)
        try:
            sync_user_pending(
                request.user,
                since_hours=720,
                dry_run=False,
                no_time_filter=True,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "[receipt] sync_user_pending failed"
            )

        txn = _find_transaction(pk, request.user)
        if not txn:
            return Response(
                {
                    "detail": (
                        "Muamala haupatikani au haujakamilika. "
                        "Receipt inapatikana kwa miamala iliyokamilika pekee."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            return self._generate_pdf(txn, request.user)
        except ImportError:
            return Response(
                {"detail": "reportlab haipo. Wasiliana na admin."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _generate_pdf(self, txn, user):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        elements = []

        title = Paragraph(
            "<b>SokoMkononi — Risiti</b>",
            styles["Title"],
        )
        elements.append(title)
        elements.append(Spacer(1, 0.2 * cm))

        subtitle = Paragraph(
            f"Risiti ya muamala · {txn['ref']}",
            styles["Normal"],
        )
        elements.append(subtitle)
        elements.append(Spacer(1, 0.8 * cm))

        amount_str = f"TZS {float(txn['amount']):,.0f}"
        
        date_str = (
            timezone.localtime(txn["date"]).strftime("%Y-%m-%d %H:%M") 
            if txn["date"] else "—"
        )
        paid_str = (
            timezone.localtime(txn["paid_at"]).strftime("%Y-%m-%d %H:%M")
            if txn["paid_at"] else "—"
        )

        info_data = [
            ["Kumbukumbu", txn["ref"]],
            ["Aina ya Muamala", txn["type_sw"]],
            ["Maelezo", txn["title"] or "—"],
            ["Kiasi", amount_str],
            ["Hali", _map_status(txn["status"])],
            ["Tarehe ya Kuunda", date_str],
            ["Tarehe ya Kulipa", paid_str],
        ]
        if txn.get("method"):
            info_data.append(["Njia ya Malipo", txn["method"]])
        if txn.get("phone"):
            info_data.append(["Namba ya Simu", txn["phone"]])

        info_table = Table(info_data, colWidths=[5 * cm, 11 * cm])
        info_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, colors.HexColor("#E6E2D6")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F3EC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 1 * cm))

        customer_name = getattr(user, "name", "") or "—"
        customer_email = getattr(user, "email", "") or "—"
        customer_phone = getattr(user, "phone", "") or "—"

        cust_data = [
            ["Mteja", customer_name],
            ["Barua pepe", customer_email],
            ["Simu", customer_phone],
        ]
        cust_table = Table(cust_data, colWidths=[5 * cm, 11 * cm])
        cust_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F3EC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(cust_table)
        elements.append(Spacer(1, 1 * cm))

        footer = Paragraph(
            "Asante kwa kutumia SokoMkononi.<br/>"
            "Hii ni risiti ya kielektroniki — hakuna sahihi inayohitajika.",
            ParagraphStyle(
                "Footer",
                parent=styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#6B7280"),
                alignment=1,
            ),
        )
        elements.append(footer)

        doc.build(elements)
        buffer.seek(0)

        response = HttpResponse(
            buffer.read(),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="receipt_{txn["ref"]}.pdf"'
        )
        return response