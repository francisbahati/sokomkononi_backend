"""
Price-drop alerts (backend, Celery beat kila dakika 10).

Kwa nini si signal ya save()?
  - Muuzaji akibadilisha bei ya tangazo LIVE/PAUSED, `perform_update`
    linarudisha tangazo PENDING_APPROVAL (price iko kwenye REVIEW_FIELDS).
    Signal ingetuma arifa kabla admin hajaidhinisha, na tangazo lisingekuwa
    la umma bado.
  - Kazi hii inaangalia tu matangazo ambayo ni LIVE SASA, kwa hiyo arifa
    inatoka baada ya idhini, bila kujali admin/approve_listing inatumia
    save() au queryset.update().

Mantiki:
  referensi = SavedListing.price_alerted ?? SavedListing.snapshot_price
  Ikiwa listing.price <= referensi * 0.99 (punguzo la >= 1%):
      1. "dai" safu kwa update ya masharti (inazuia arifa mbili)
      2. tuma notification PRICE_DROP
  snapshot_price HAIBADILIKI (frontend bado inaweza kuonyesha
  "imeshuka tangu uhifadhi"); tunasasisha price_alerted tu.

Jaribu kwa mkono:
  python manage.py shell -c "from apps.listings.price_drop import run_price_drop_check as r; print(r())"
"""
import logging
from decimal import Decimal

from celery import shared_task
from django.db.models import F
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _, override

from .models import Listing

logger = logging.getLogger(__name__)

MIN_DROP_RATIO = Decimal("0.99")  # punguzo la angalau 1%


@shared_task(name="listings.notify_price_drops", ignore_result=True)
def notify_price_drops():
    return run_price_drop_check()


def run_price_drop_check():
    from apps.notifications.models import Notification
    from apps.notifications.services.notification import create_notification
    from apps.saved.models import SavedListing
    from apps.transactions.services._lang import user_lang

    qs = (
        SavedListing.objects
        .filter(
            listing__status=Listing.Status.LIVE,
            listing__is_deleted=False,
            listing__price__gt=0,
            user__is_active=True,
        )
        .exclude(user_id=F("listing__seller_id"))
        .annotate(ref_price=Coalesce("price_alerted", "snapshot_price"))
        .filter(
            ref_price__isnull=False,
            ref_price__gt=0,
            listing__price__lte=F("ref_price") * MIN_DROP_RATIO,
        )
        .select_related("listing", "user")
    )

    sent = skipped = 0
    for saved in qs.iterator(chunk_size=200):
        listing, user = saved.listing, saved.user
        old_price = saved.ref_price
        new_price = listing.price
        try:
            # "Dai": ni mwito mmoja tu utakaofaulu hata workers zikikimbia pamoja.
            claimed = SavedListing.objects.filter(
                pk=saved.pk, price_alerted=saved.price_alerted,
            ).update(price_alerted=new_price)
            if claimed != 1:
                skipped += 1
                continue

            pct = int((Decimal(old_price) - Decimal(new_price)) / Decimal(old_price) * 100)
            with override(user_lang(user)):
                create_notification(
                    recipient=user,
                    notification_type=Notification.NotificationType.PRICE_DROP,
                    title=_("Bei Imeshuka!"),
                    message=_(
                        "Bei ya '{title}' uliyohifadhi imeshuka kutoka "
                        "TZS {old} hadi TZS {new} (-{pct}%)."
                    ).format(
                        title=listing.title,
                        old=f"{Decimal(old_price):,.0f}",
                        new=f"{Decimal(new_price):,.0f}",
                        pct=pct,
                    ),
                    priority=Notification.Priority.NORMAL,
                    related_object_type="Listing",
                    related_object_id=listing.pk,
                    action_url=f"/mali/{listing.pk}",
                )
            sent += 1
        except Exception:
            logger.exception("price-drop: failed saved=%s", saved.pk)
    return {"sent": sent, "skipped": skipped}