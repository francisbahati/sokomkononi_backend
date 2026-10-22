# apps/payments/management/commands/reconcile_payments.py
"""
Rekebisha malipo ambayo FimiPay iliyapokea lakini SokoMkononi haikuyatumia
(webhook ilikataliwa au haikufika) — kwa AINA ZOTE za malipo:
listing fee (LSF), boost (BST), leading (LDS), bundle (BND),
advertise (ADV), success fee/ripoti (SFE), reservation (RSV).

Hatua:
  1. WebhookDiscrepancy zote ambazo hazijatatuliwa (no_db_record,
     amount_mismatch, missing_amount): linganisha kiasi kilichoripotiwa na
     kiasi kilichohifadhiwa kwenye DB (kwa kutumia lookup sahihi ya kila aina),
     kisha itumie kupitia handler ile ile ya webhook (idempotent).
  2. ListingFee zilizo PENDING zenye order ya "LSF-..." -> uliza FimiPay
     hali ya order; kama SUCCESS, itumie.

Matumizi (dry-run ndiyo chaguo-msingi, haibadilishi chochote):
    python manage.py reconcile_payments
    python manage.py reconcile_payments --apply
    python manage.py reconcile_payments --prefix BND --apply

Weka folda `management/` na `commands/` ndani ya apps/payments, kila moja
ikiwa na faili tupu `__init__.py`.
"""
import importlib
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand

from apps.payments.fimipay import get_order_status
from apps.payments.models import WebhookDiscrepancy
from apps.payments.order_ids import parse_order_id
from apps.payments.views import _SUCCESS_HANDLERS, _lookup_expected_amount


def _dec(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _call_handler(prefix, ref_id, payment_reference):
    module_path, func_name = _SUCCESS_HANDLERS[prefix]
    handler = getattr(importlib.import_module(module_path), func_name)
    return handler(ref_id=ref_id, payment_reference=payment_reference)


class Command(BaseCommand):
    help = "Recover payments received by FimiPay but never applied (all types)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Tumia malipo kweli (bila hii ni dry-run).")
        parser.add_argument("--prefix", default="",
                            help="Punguza kwa aina moja, mf. LSF, BND, RSV.")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        only = (opts["prefix"] or "").upper()
        self.stdout.write(self.style.WARNING(
            f"== reconcile_payments [{'APPLY' if apply else 'DRY-RUN'}] "
            f"{('prefix=' + only) if only else 'all prefixes'} =="
        ))
        fixed = self._from_discrepancies(apply, only)
        if not only or only == "LSF":
            fixed += self._from_pending_listing_fees(apply)
        self.stdout.write(self.style.SUCCESS(f"Imekamilika. Zilizorekebishwa: {fixed}"))

    # ----------------------------------------------------------
    def _from_discrepancies(self, apply, only):
        fixed = 0
        qs = WebhookDiscrepancy.objects.filter(
            resolved=False,
            reason__in=["no_db_record", "amount_mismatch", "missing_amount"],
        ).order_by("created_at")
        if only:
            qs = qs.filter(prefix=only)

        self.stdout.write(f"\n[1] WebhookDiscrepancy zisizotatuliwa: {qs.count()}")
        seen = set()
        for d in qs:
            if d.order_id in seen:
                continue  # webhook ileile inaweza kuwa imeandikwa mara nyingi
            seen.add(d.order_id)

            prefix, ref_id = parse_order_id(d.order_id)
            if prefix not in _SUCCESS_HANDLERS or ref_id is None:
                self.stdout.write(self.style.ERROR(
                    f"  - {d.order_id}: aina haina handler -> angalia kwa mkono"
                ))
                continue

            try:
                expected = _dec(_lookup_expected_amount(prefix, ref_id))
            except Exception as exc:
                self.stdout.write(f"  - {d.order_id}: lookup imeshindwa ({exc}) -> ruka")
                continue
            if expected is None:
                self.stdout.write(self.style.ERROR(
                    f"  - {d.order_id}: rekodi ya DB haipo -> angalia kwa mkono"
                ))
                continue

            payload = d.raw_payload or {}
            reported = _dec(payload.get("amount"))
            if reported is None or reported != expected:
                self.stdout.write(self.style.ERROR(
                    f"  - {d.order_id}: kiasi hakilingani "
                    f"(FimiPay={reported}, DB={expected}) -> angalia kwa mkono"
                ))
                continue

            self.stdout.write(self.style.SUCCESS(
                f"  - {d.order_id}: kiasi sawa ({expected}) -> "
                f"{'itumie' if apply else 'ingetumika'}"
            ))
            if apply:
                _call_handler(prefix, ref_id, payload.get("transid") or d.order_id)
                WebhookDiscrepancy.objects.filter(
                    order_id=d.order_id, resolved=False,
                ).update(resolved=True,
                         resolution_note="Applied by reconcile_payments.")
            fixed += 1
        return fixed

    # ----------------------------------------------------------
    def _from_pending_listing_fees(self, apply):
        from apps.listings.models import ListingFee

        fixed = 0
        qs = ListingFee.objects.filter(
            payment_status=ListingFee.PaymentStatus.PENDING,
            payment_reference__startswith="LSF-",
        ).order_by("created_at")

        self.stdout.write(f"\n[2] ListingFee PENDING zenye order ya FimiPay: {qs.count()}")
        for fee in qs:
            ref = fee.payment_reference
            prefix, ref_id = parse_order_id(ref)
            if prefix != "LSF" or ref_id is None:
                continue
            try:
                data = get_order_status(ref)
            except Exception as exc:
                self.stdout.write(f"  - {ref}: FimiPay haikujibu ({exc}) -> ruka")
                continue
            status = str(data.get("payment_status") or "").upper()
            if status != "SUCCESS":
                self.stdout.write(f"  - {ref}: {status or 'bila status'} -> ruka")
                continue
            self.stdout.write(self.style.SUCCESS(
                f"  - {ref}: SUCCESS -> {'itumie' if apply else 'ingetumika'}"
            ))
            if apply:
                _call_handler("LSF", ref_id, data.get("transid") or ref)
            fixed += 1
        return fixed