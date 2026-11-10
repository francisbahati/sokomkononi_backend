"""
Search alerts (backend, Celery beat kila dakika 5).
"""
import logging
from datetime import timedelta
from urllib.parse import quote

from celery import shared_task
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.translation import gettext as _, override

from apps.listings.models import Listing

from .models import SavedSearch, SavedSearchMatch

logger = logging.getLogger(__name__)

LOOKBACK = timedelta(hours=24)
INDIVIDUAL_CAP = 5
MAX_FRESH_PER_RUN = 100
MAX_QUERY_WORDS = 6


@shared_task(name="searches.send_search_alerts", ignore_result=True)
def send_search_alerts():
    return run_search_alerts()


def _criteria_qs(search):
    """Matangazo yanayolingana na vigezo vya utafutaji (bila dedupe/muda)."""
    qs = (
        Listing.objects
        .filter(status=Listing.Status.LIVE, is_deleted=False)
        .exclude(seller_id=search.user_id)
    )
    if search.category_slug:
        qs = qs.filter(category__slug=search.category_slug)
    if search.region:
        # Listing haina field ya region; `location` ni maandishi kamili
        # (mf. "Dar es Salaam, Kinondoni"), kwa hiyo icontains.
        qs = qs.filter(location__icontains=search.region)
    if search.min_price is not None:
        qs = qs.filter(price__gte=search.min_price)
    if search.max_price is not None:
        qs = qs.filter(price__lte=search.max_price)
    if search.verified_only:
        qs = qs.filter(seller__is_verified=True)
    # Kila neno lazima litokee kwenye kichwa, maelezo au mahali.
    for word in (search.query or "").split()[:MAX_QUERY_WORDS]:
        qs = qs.filter(
            Q(title__icontains=word)
            | Q(description__icontains=word)
            | Q(location__icontains=word)
        )
    return qs


def _search_url(search):
    q = (search.query or "").strip()
    return f"/tafuta?tafuta={quote(q)}" if q else "/mali-zote"


def _notify_individual(user, search, listing):
    from apps.notifications.models import Notification
    from apps.notifications.services.notification import create_notification
    from apps.transactions.services._lang import user_lang

    with override(user_lang(user)):
        create_notification(
            recipient=user,
            notification_type=Notification.NotificationType.SEARCH_ALERT,
            title=_("Tangazo jipya linafanana na utafutaji wako"),
            message=_("\"{name}\": {title} — TZS {price}").format(
                name=search.name,
                title=listing.title,
                price=f"{listing.price:,.0f}",
            ),
            priority=Notification.Priority.NORMAL,
            related_object_type="Listing",
            related_object_id=listing.pk,
            action_url=f"/mali/{listing.pk}",
        )


def _notify_digest(user, search, count):
    from apps.notifications.models import Notification
    from apps.notifications.services.notification import create_notification
    from apps.transactions.services._lang import user_lang

    with override(user_lang(user)):
        create_notification(
            recipient=user,
            notification_type=Notification.NotificationType.SEARCH_ALERT,
            title=_("Matangazo mapya yanafanana na utafutaji wako"),
            message=_(
                "\"{name}\": matangazo {n} mapya yanafanana na utafutaji wako."
            ).format(name=search.name, n=count),
            priority=Notification.Priority.NORMAL,
            related_object_type="",
            related_object_id=None,
            action_url=_search_url(search),
        )


def _process(search, now):
    base = _criteria_qs(search)
    floor = max(search.created_at, now - LOOKBACK)

    fresh = list(
        base.annotate(go_live=Coalesce("approved_at", "created_at"))
        .filter(go_live__gte=floor)
        .exclude(search_matches__search_id=search.pk)
        .order_by("go_live")[:MAX_FRESH_PER_RUN]
    )

    # "Dai" kila tangazo kupitia unique constraint (hakuna arifa mbili
    # hata workers zikikimbia pamoja).
    claimed = []
    for listing in fresh:
        _, created = SavedSearchMatch.objects.get_or_create(
            search=search, listing=listing,
        )
        if created:
            claimed.append(listing)

    sent = 0
    if claimed:
        if len(claimed) <= INDIVIDUAL_CAP:
            for listing in claimed:
                _notify_individual(search.user, search, listing)
                sent += 1
        else:
            _notify_digest(search.user, search, len(claimed))
            sent = 1

    SavedSearch.objects.filter(pk=search.pk).update(
        match_count=base.count(), last_checked=now,
    )
    return sent, len(claimed)


def run_search_alerts():
    now = timezone.now()
    searches = (
        SavedSearch.objects
        .filter(user__is_active=True)
        .select_related("user")
    )
    notifications = matched = failed = 0
    for search in searches.iterator(chunk_size=200):
        try:
            n, m = _process(search, now)
            notifications += n
            matched += m
        except Exception:
            failed += 1
            logger.exception("search-alerts: failed search=%s", search.pk)
    return {"notifications": notifications, "matched": matched, "failed": failed}