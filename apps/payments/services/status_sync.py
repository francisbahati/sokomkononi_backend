import importlib, logging
from datetime import timedelta
from django.db import connection
from django.utils import timezone
from apps.payments.fimipay import get_order_status

logger = logging.getLogger(__name__)
SYNC_SOURCES = [
    {"model":"listings.ListingFee","pending_field":"payment_status","pending_value":"PENDING",
     "reference_field":"payment_reference","user_field":"seller",
     "ref_attr":"listing_id",
     "handler":("apps.listings.services.listing_payment","mark_listing_fee_as_paid_from_webhook")},
    {"model":"boosting.ListingBoost","pending_field":"payment_status","pending_value":"PENDING",
     "reference_field":"payment_reference","user_field":"seller",
     "handler":("apps.boosting.services.boost","mark_boost_as_paid_from_webhook")},
    {"model":"leading_fees.ListingLeading","pending_field":"payment_status","pending_value":"PENDING",
     "reference_field":"payment_reference","user_field":"seller",
     "handler":("apps.leading_fees.services.leading","mark_leading_paid_from_webhook")},
    {"model":"bundles.BundlePurchase","pending_field":"status","pending_value":"PENDING",
     "reference_field":"payment_reference","user_field":"user",
     "handler":("apps.bundles.services","mark_purchase_paid_from_webhook")},
    {"model":"banners.BannerAd","pending_field":"payment_status","pending_value":"PENDING",
     "reference_field":"payment_reference","user_field":"seller",
     "handler":("apps.banners.services","mark_banner_paid_from_webhook")},
    {"model":"finance.SuccessFeePayment","pending_field":"payment_status","pending_value":"PENDING",
     "reference_field":"payment_reference","user_field":"user",
     "handler":("apps.finance.services_success_fee","mark_success_fee_paid_from_webhook")},
    {"model":"transactions.Reservation","pending_field":"payment_status","pending_value":"PENDING",
     "reference_field":"payment_reference","user_field":"transaction__buyer",
     "handler":("apps.transactions.services.reservation","mark_reservation_paid_from_webhook")},
]

def _ensure_db():
    try: connection.ensure_connection()
    except Exception as e:
        logger.warning("db reconnect: %s", e); connection.close(); connection.ensure_connection()

def _get_model(path):
    from django.apps import apps
    a, m = path.split("."); return apps.get_model(a, m)

def _fimipay_success(ref):
    if not ref: return False
    try: d = get_order_status(ref)
    except Exception as e: logger.warning("get_order_status %s: %s", ref, e); return False
    return str(d.get("payment_status") or "").upper() == "SUCCESS"

def _sync_source(src, user=None, since_hours=48, dry_run=False, no_time_filter=False):
    M = _get_model(src["model"])
    f = {src["pending_field"]: src["pending_value"]}
    if not no_time_filter: f["created_at__gte"] = timezone.now() - timedelta(hours=since_hours)
    if user: f[src["user_field"]] = user
    _ensure_db()
    try:
        objs = list(M.objects.filter(**f).exclude(**{f"{src['reference_field']}__isnull": True}).exclude(**{src["reference_field"]: ""}))
    except Exception:
        _ensure_db()
        objs = list(M.objects.filter(**f).exclude(**{f"{src['reference_field']}__isnull": True}).exclude(**{src["reference_field"]: ""}))
    checked = updated = errors = 0
    mod, fn = src["handler"]
    for o in objs:
        checked += 1
        ref = getattr(o, src["reference_field"], None)
        if not ref: continue
        try:
            if _fimipay_success(ref):
                if dry_run:
                    updated += 1
                else:
                    ref_id = getattr(o, src.get("ref_attr", "pk"))
                    result = getattr(importlib.import_module(mod), fn)(
                        ref_id=ref_id, payment_reference=ref,
                    )
                    # Handler inarudisha None kama rekodi haikupatikana:
                    # usihesabu hiyo kama "updated".
                    if result is not None:
                        updated += 1
                    else:
                        logger.warning(
                            "sync %s#%s: handler returned None (ref_id=%s)",
                            src["model"], o.pk, ref_id,
                        )
        except Exception:
            errors += 1; logger.exception("sync %s#%s failed", src["model"], o.pk)
    return {"checked": checked, "updated": updated, "errors": errors}

def sync_all_pending(since_hours=48, dry_run=False, no_time_filter=False):
    out = {}; c = u = 0
    for s in SYNC_SOURCES:
        try:
            r = _sync_source(s, None, since_hours, dry_run, no_time_filter)
            out[s["model"]] = r; c += r["checked"]; u += r["updated"]
        except Exception as e:
            logger.exception("source %s failed", s["model"]); out[s["model"]] = {"error": str(e)}
    return {"total_checked": c, "total_updated": u, "by_source": out}

def sync_user_pending(user, since_hours=48, dry_run=False, no_time_filter=False):
    out = {}; c = u = 0
    for s in SYNC_SOURCES:
        try:
            r = _sync_source(s, user, since_hours, dry_run, no_time_filter)
            out[s["model"]] = r; c += r["checked"]; u += r["updated"]
        except Exception as e:
            logger.exception("user=%s source=%s failed", user.id, s["model"]); out[s["model"]] = {"error": str(e)}
    return {"total_checked": c, "total_updated": u, "by_source": out}