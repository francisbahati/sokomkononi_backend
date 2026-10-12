# apps/payments/services/status_sync.py
"""
FimiPay status sync — shared logic.

Inatumika na:
  - Webhook handler (primary)
  - Celery periodic task (fallback)
  - Download endpoint (on-demand)

Inaangalia FimiPay kwa PENDING orders na ku-update statuses.

SASISHO:
  - `no_time_filter=True` — sync zote PENDING bila kujali muda (manual)
  - `_ensure_db_connection()` — reconnect kama DB connection imekatika
"""
import logging
from datetime import timedelta

from django.db import connection
from django.utils import timezone

from apps.payments.fimipay import get_order_status

logger = logging.getLogger(__name__)


# ============================================================
# DB CONNECTION HEALTH
# ============================================================
def _ensure_db_connection():
    """
    Hakikisha database connection ipo. Kama imekatika, reconnect.
    Inaitwa kabla ya kila query muhimu.
    """
    try:
        connection.ensure_connection()
    except Exception as e:
        logger.warning(f"[fimipay sync] DB connection failed, reconnecting: {e}")
        try:
            connection.close()
            connection.ensure_connection()
        except Exception as e2:
            logger.exception(f"[fimipay sync] DB reconnect failed: {e2}")
            raise


# ============================================================
# SYNC SOURCES
# ============================================================
SYNC_SOURCES = [
    {
        "model": "listings.ListingFee",
        "payment_status_field": "payment_status",
        "paid_at_field": "paid_at",
        "pending_value": "PENDING",
        "paid_value": "PAID",
        "reference_field": "payment_reference",
        "user_field": "seller",
    },
    {
        "model": "boosting.ListingBoost",
        "payment_status_field": "payment_status",
        "paid_at_field": "paid_at",
        "pending_value": "PENDING",
        "paid_value": "PAID",
        "reference_field": "payment_reference",
        "user_field": "seller",
    },
    {
        "model": "bundles.BundlePurchase",
        "payment_status_field": "status",
        "paid_at_field": "paid_at",
        "pending_value": "PENDING",
        "paid_value": "PAID",
        "reference_field": "payment_reference",
        "user_field": "user",
    },
    {
        "model": "banners.BannerAd",
        "payment_status_field": "payment_status",
        "paid_at_field": "paid_at",
        "pending_value": "PENDING",
        "paid_value": "PAID",
        "reference_field": "payment_reference",
        "user_field": "seller",
    },
    {
        "model": "finance.SuccessFeePayment",
        "payment_status_field": "payment_status",
        "paid_at_field": "paid_at",
        "pending_value": "PENDING",
        "paid_value": "PAID",
        "reference_field": "payment_reference",
        "user_field": "user",
    },
    {
        "model": "leading_fees.ListingLeading",
        "payment_status_field": "payment_status",
        "paid_at_field": "paid_at",
        "pending_value": "PENDING",
        "paid_value": "PAID",
        "reference_field": "payment_reference",
        "user_field": "seller",
    },
]


# ============================================================
# HELPERS
# ============================================================
def _get_model(dotted_path):
    from django.apps import apps
    app_label, model_name = dotted_path.split(".")
    return apps.get_model(app_label, model_name)


def _fimipay_is_success(reference):
    """Angalia FimiPay kama order ni SUCCESS. Inarudisha bool."""
    if not reference:
        return False
    try:
        data = get_order_status(reference)
    except Exception as e:
        logger.warning(f"[fimipay sync] get_order_status failed for {reference}: {e}")
        return False

    status = str(data.get("payment_status") or "").upper()
    return status == "SUCCESS"


def _has_updated_at(obj):
    return hasattr(obj, "updated_at")


# ============================================================
# CORE SYNC — chanzo kimoja
# ============================================================
def _sync_source(source, user=None, since_hours=48, dry_run=False, no_time_filter=False):
    """
    Sync chanzo kimoja.

    Args:
        source: dict kutoka SYNC_SOURCES
        user: kama ipo, sync user huyu pekee
        since_hours: angalia orders za saa ngapi zilizopita
        dry_run: kama True, usiandike database
        no_time_filter: kama True, puuza `created_at` filter (sync zote)
    """
    Model = _get_model(source["model"])

    filters = {
        source["payment_status_field"]: source["pending_value"],
    }
    if not no_time_filter:
        since = timezone.now() - timedelta(hours=since_hours)
        filters["created_at__gte"] = since
    if user:
        filters[source["user_field"]] = user

    # Ensure DB connection
    _ensure_db_connection()

    # Chukua list yote kwa mara moja
    try:
        objects = list(
            Model.objects
            .filter(**filters)
            .exclude(**{f"{source['reference_field']}__isnull": True})
            .exclude(**{source["reference_field"]: ""})
        )
    except Exception as e:
        logger.warning(
            f"[fimipay sync] Query failed for {source['model']}, retrying: {e}"
        )
        _ensure_db_connection()
        objects = list(
            Model.objects
            .filter(**filters)
            .exclude(**{f"{source['reference_field']}__isnull": True})
            .exclude(**{source["reference_field"]: ""})
        )

    checked = 0
    updated = 0
    errors = 0

    for obj in objects:
        checked += 1
        ref = getattr(obj, source["reference_field"], None)
        if not ref:
            continue

        try:
            if _fimipay_is_success(ref):
                if not dry_run:
                    _ensure_db_connection()

                    setattr(
                        obj,
                        source["payment_status_field"],
                        source["paid_value"],
                    )
                    setattr(obj, source["paid_at_field"], timezone.now())

                    update_fields = [
                        source["payment_status_field"],
                        source["paid_at_field"],
                    ]
                    if _has_updated_at(obj):
                        update_fields.append("updated_at")

                    try:
                        obj.save(update_fields=update_fields)
                    except Exception as save_err:
                        logger.warning(
                            f"[fimipay sync] Save failed for {source['model']} "
                            f"#{obj.pk}, retrying: {save_err}"
                        )
                        _ensure_db_connection()
                        obj.save(update_fields=update_fields)

                updated += 1
                logger.info(
                    f"[fimipay sync] {source['model']} #{obj.pk} "
                    f"({ref}) → {source['paid_value']}"
                )
        except Exception as e:
            errors += 1
            logger.exception(
                f"[fimipay sync] {source['model']} #{obj.pk} failed: {e}"
            )

    return {"checked": checked, "updated": updated, "errors": errors}


# ============================================================
# PUBLIC API
# ============================================================
def sync_all_pending(since_hours=48, dry_run=False, no_time_filter=False):
    """Sync vyanzo vyote kwa PENDING orders."""
    by_source = {}
    total_checked = 0
    total_updated = 0

    for source in SYNC_SOURCES:
        try:
            result = _sync_source(
                source,
                user=None,
                since_hours=since_hours,
                dry_run=dry_run,
                no_time_filter=no_time_filter,
            )
            by_source[source["model"]] = result
            total_checked += result["checked"]
            total_updated += result["updated"]
        except Exception as e:
            logger.exception(f"[fimipay sync] source {source['model']} failed: {e}")
            by_source[source["model"]] = {"error": str(e)}

    return {
        "total_checked": total_checked,
        "total_updated": total_updated,
        "by_source": by_source,
    }


def sync_user_pending(user, since_hours=48, dry_run=False, no_time_filter=False):
    """Sync vyanzo vyote kwa user mmoja."""
    by_source = {}
    total_checked = 0
    total_updated = 0

    for source in SYNC_SOURCES:
        try:
            result = _sync_source(
                source,
                user=user,
                since_hours=since_hours,
                dry_run=dry_run,
                no_time_filter=no_time_filter,
            )
            by_source[source["model"]] = result
            total_checked += result["checked"]
            total_updated += result["updated"]
        except Exception as e:
            logger.exception(
                f"[fimipay sync] user={user.id} source={source['model']} failed: {e}"
            )
            by_source[source["model"]] = {"error": str(e)}

    return {
        "total_checked": total_checked,
        "total_updated": total_updated,
        "by_source": by_source,
    }