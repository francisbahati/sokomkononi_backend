# ============================================================
# apps/categories/stats.py   (FILE MPYA)
#
# Helpers za kuhesabu listings kwa kila category.
#
# Hatujapewa apps/listings/models.py, kwa hiyo model ya Listing
# na field ya FK kwenda Category zinatambuliwa kiotomatiki.
# Kama jina la app/model ni tofauti, badilisha LISTING_MODEL_LABEL.
# ============================================================
from datetime import timedelta

from django.apps import apps
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Category

LISTING_MODEL_LABEL = ("listings", "Listing")


def _listing_model():
    try:
        return apps.get_model(*LISTING_MODEL_LABEL)
    except LookupError:
        return None


def _category_fk_name(Listing):
    for f in Listing._meta.get_fields():
        if f.is_relation and f.many_to_one and f.related_model is Category:
            return f.name
    return None


def _field_names(Model):
    return {f.name for f in Model._meta.get_fields()}


def listing_queryset():
    """
    Returns (queryset, fk_name) ya listings zote ambazo hazijafutwa,
    au (None, None) kama model haipatikani.
    """
    Listing = _listing_model()
    if Listing is None:
        return None, None
    fk = _category_fk_name(Listing)
    if not fk:
        return None, None
    qs = Listing.objects.all()
    if "is_deleted" in _field_names(Listing):
        qs = qs.filter(is_deleted=False)
    return qs, fk


def annotate_listings_count(category_qs):
    """Ongeza `listings_count` (annotation) kwenye queryset ya Category."""
    qs, fk = listing_queryset()
    if qs is None:
        return category_qs
    sub = (
        qs.filter(**{fk: OuterRef("pk")})
        .order_by()
        .values(fk)
        .annotate(c=Count("pk"))
        .values("c")
    )
    return category_qs.annotate(
        listings_count=Coalesce(Subquery(sub), 0)
    )


def count_for(category_id):
    """Idadi ya listings za category moja (fallback ya serializer)."""
    qs, fk = listing_queryset()
    if qs is None:
        return None
    return qs.filter(**{fk: category_id}).count()


def build_stats(days=30):
    """
    Takwimu kwa kila category:
      total, by_status (kama Listing ina `status`),
      new_recent (kama ina `created_at`), views (kama ina field ya views).
    """
    qs, fk = listing_queryset()
    if qs is None:
        return {"available": False, "categories": [], "totals": {}}

    Listing = qs.model
    fields = _field_names(Listing)
    since = timezone.now() - timedelta(days=days)

    agg = {"total": Count("pk")}
    if "created_at" in fields:
        agg["new_recent"] = Count("pk", filter=Q(created_at__gte=since))

    views_field = next(
        (n for n in ("views_count", "views", "view_count") if n in fields),
        None,
    )

    rows = {
        r[fk]: r for r in qs.order_by().values(fk).annotate(**agg)
    }

    by_status = {}
    if "status" in fields:
        for r in (
            qs.order_by().values(fk, "status").annotate(c=Count("pk"))
        ):
            by_status.setdefault(r[fk], {})[r["status"] or "unknown"] = r["c"]

    views = {}
    if views_field:
        from django.db.models import Sum
        for r in qs.order_by().values(fk).annotate(v=Sum(views_field)):
            views[r[fk]] = r["v"] or 0

    out = []
    for cat in Category.objects.all().order_by("ordering", "name"):
        r = rows.get(cat.id, {})
        out.append({
            "id": cat.id,
            "slug": cat.slug,
            "name": cat.name,
            "total": r.get("total", 0),
            "new_recent": r.get("new_recent", 0),
            "views": views.get(cat.id, 0),
            "by_status": by_status.get(cat.id, {}),
        })

    totals = {
        "categories": len(out),
        "listings": sum(c["total"] for c in out),
        "empty": sum(1 for c in out if c["total"] == 0),
        "new_recent": sum(c["new_recent"] for c in out),
        "views": sum(c["views"] for c in out),
    }
    return {
        "available": True,
        "days": days,
        "has_status": "status" in fields,
        "has_views": bool(views_field),
        "has_created_at": "created_at" in fields,
        "categories": out,
        "totals": totals,
    }
