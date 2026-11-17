# ============================================================
# apps/announcements/services.py   (FILE MPYA)
#
# - Kanuni ya "imetumwa" (is_published / published_q / sync_due)
# - Utoaji wa arifa kwa watumiaji wote hai, njia tatu:
#     1. Bell (Notification ya ndani) — kwa kila mtumiaji hai, bulk.
#     2. Push  — kupitia notifications.services.notification._send_via_channel
#     3. Email — kupitia notifications.services.notification._send_via_channel
#   Push na email zinatumwa kwa chunks za Celery (tasks.send_channels)
#   ili mtumiaji mmoja mwenye tatizo asivunje wengine na task isiwe ndefu.
#
# Prefs za mtumiaji:
#   PROMOTION / NEW_CATEGORY  → zinaheshimu `push_promotions` / `email_promotions`
#   MAINTENANCE / FEE_CHANGE  → matangazo ya mfumo: yanatumwa kwa wote
#   (Bell inaundwa kila wakati, kama create_notification ya mradi.)
#
# Usalama wa kutuma mara moja tu:
#  - `dispatched_at` inadaiwa (claim) kwa UPDATE ya atomic; mtu wa
#    kwanza tu ndiye anayeendelea.
#  - Bell: hitilafu ikitokea, claim inarudishwa; retry inaruka walioshapata
#    bell (hakuna nakala).
#  - Push/email zinatumwa kwa watumiaji WAPYA wa bell tu na kamwe
#    hazirudiwi (at-most-once): hatuna jedwali la delivery, na kurudia
#    kungetuma email/push mbili.
# ============================================================
import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Announcement

logger = logging.getLogger(__name__)

RELATED_TYPE = "announcement"
BATCH_SIZE = 500
CHANNEL_CHUNK = 200
CHANNELS = ("push", "email")

# Aina ya tangazo → category ya prefs (None = tangazo la mfumo, tuma kwa wote)
PREF_CATEGORY = {
    Announcement.Type.PROMOTION: "promotions",
    Announcement.Type.NEW_CATEGORY: "promotions",
    Announcement.Type.FEE_CHANGE: None,
    Announcement.Type.MAINTENANCE: None,
}

# Sweeper (dispatch_pending) inashughulikia matangazo ya saa 24 zilizopita
# tu. Inalinda dhidi ya kutuma arifa za matangazo ya zamani kwa bahati
# mbaya (mfano baada ya migration, kabla ya backfill).
DISPATCH_WINDOW = timedelta(hours=24)


# ------------------------------------------------------------
# KANUNI YA "IMETUMWA"
# ------------------------------------------------------------
def is_published(obj, now=None):
    """Ina ratiba → muda umefika; haina ratiba → sent=True."""
    now = now or timezone.now()
    if obj.scheduled_for:
        return obj.scheduled_for <= now
    return bool(obj.sent)


def published_q(now):
    """Lazima ilingane na is_published()."""
    return Q(scheduled_for__lte=now) | Q(scheduled_for__isnull=True, sent=True)


def sync_due(now):
    """Sawazisha flag `sent` kwa matangazo yaliyofikia muda wake."""
    return Announcement.objects.filter(
        sent=False, scheduled_for__lte=now,
    ).update(sent=True)


# ------------------------------------------------------------
# MAUDHUI
# ------------------------------------------------------------
def _lang_field(User):
    """Jina la field ya lugha kwenye User model, kama ipo."""
    names = {f.name for f in User._meta.get_fields()}
    for candidate in ("language", "preferred_language", "lang"):
        if candidate in names:
            return candidate
    return None


def _content_for(obj, lang):
    if str(lang or "").lower().startswith("en") and (obj.title_en or obj.message_en):
        return (obj.title_en or obj.title), (obj.message_en or obj.message)
    return obj.title, obj.message


def _channel_allowed(user, ann_type, channel):
    """Prefs za mtumiaji (kama _should_send_via_channel ya notifications)."""
    category = PREF_CATEGORY.get(ann_type)
    if category is None:
        return True  # tangazo la mfumo
    try:
        prefs = user.notification_preferences
    except Exception:
        return True
    field = f"{channel}_{category}"
    if not hasattr(prefs, field):
        return True
    return bool(getattr(prefs, field))


# ------------------------------------------------------------
# BELL (bulk, idempotent kwa kila mpokeaji)
# ------------------------------------------------------------
def _fan_out(obj):
    """
    Unda Notification ya ndani kwa kila mtumiaji hai.
    Inarudisha ids za watumiaji WAPYA (walioundiwa sasa).
    """
    from apps.notifications.models import Notification

    User = get_user_model()
    lang_field = _lang_field(User)
    fields = ["id"] + ([lang_field] if lang_field else [])

    priority = (
        Notification.Priority.HIGH
        if obj.type == Announcement.Type.MAINTENANCE
        else Notification.Priority.NORMAL
    )

    new_ids = []

    def flush(batch):
        ids = [row[0] for row in batch]
        already = set(
            Notification.all_objects.filter(
                related_object_type=RELATED_TYPE,
                related_object_id=obj.id,
                recipient_id__in=ids,
            ).values_list("recipient_id", flat=True)
        )
        rows = []
        for row in batch:
            if row[0] in already:
                continue
            title, message = _content_for(obj, row[1] if lang_field else None)
            rows.append(
                Notification(
                    recipient_id=row[0],
                    notification_type=Notification.NotificationType.GENERAL,
                    title=title[:255],
                    message=message,
                    priority=priority,
                    audience=Notification.Audience.USER,
                    side=Notification.Side.BOTH,
                    related_object_type=RELATED_TYPE,
                    related_object_id=obj.id,
                    action_url="",
                )
            )
            new_ids.append(row[0])
        if rows:
            Notification.objects.bulk_create(rows, batch_size=BATCH_SIZE)

    batch = []
    users = User.objects.filter(is_active=True).order_by("id").values_list(*fields)
    for row in users.iterator(chunk_size=2000):
        batch.append(row)
        if len(batch) >= BATCH_SIZE:
            flush(batch)
            batch = []
    if batch:
        flush(batch)
    return new_ids


# ------------------------------------------------------------
# PUSH + EMAIL (chunk moja, inaitwa na tasks.send_channels)
# ------------------------------------------------------------
def deliver_channels(announcement_id, user_ids):
    """
    Tuma push na email kwa watumiaji wa chunk hii, ukizingatia prefs.
    Kila mtumiaji/channel ina try/except yake — hitilafu moja haivunji wengine.
    Inarudisha {"push": n, "email": n, "skipped": n, "errors": n}.
    """
    from apps.notifications.services.notification import _send_via_channel

    try:
        obj = Announcement.objects.get(pk=announcement_id)
    except Announcement.DoesNotExist:
        return {"push": 0, "email": 0, "skipped": 0, "errors": 0, "missing": True}

    User = get_user_model()
    lang_field = _lang_field(User)
    users = (
        User.objects.filter(pk__in=list(user_ids), is_active=True)
        .select_related("notification_preferences")
    )

    stats = {"push": 0, "email": 0, "skipped": 0, "errors": 0}
    for user in users:
        title, message = _content_for(obj, getattr(user, lang_field, None) if lang_field else None)
        for channel in CHANNELS:
            if not _channel_allowed(user, obj.type, channel):
                stats["skipped"] += 1
                continue
            try:
                ok = _send_via_channel(
                    channel=channel,
                    recipient=user,
                    title=title,
                    message=message,
                    # tag ya push inatokana na hii → kila tangazo lina tag yake,
                    # matangazo hayafutani kwenye kifaa
                    notification_type=f"announcement-{obj.id}",
                    action_url="",
                )
                if ok:
                    stats[channel] += 1
                else:
                    stats["skipped"] += 1  # hana email/token ya push, n.k.
            except Exception:
                stats["errors"] += 1
                logger.exception(
                    "announcement %s: %s failed for user %s", obj.id, channel, user.pk,
                )
    return stats


def _enqueue_channels(announcement_id, user_ids):
    """Gawanya kwa chunks na uzipeleke kwenye Celery. Inarudisha idadi ya chunks."""
    from .tasks import send_announcement_channels

    chunks = 0
    for i in range(0, len(user_ids), CHANNEL_CHUNK):
        send_announcement_channels.delay(announcement_id, user_ids[i:i + CHANNEL_CHUNK])
        chunks += 1
    return chunks


# ------------------------------------------------------------
# DISPATCH
# ------------------------------------------------------------
def dispatch_announcement(announcement_id):
    """
    Tuma tangazo kwa watumiaji (bell + push + email) — mara moja tu.
    Inarudisha {"status": "sent"|"skipped", ...}.
    """
    now = timezone.now()

    # Claim ya atomic: mmoja tu anashinda.
    claimed = Announcement.objects.filter(
        pk=announcement_id, dispatched_at__isnull=True,
    ).update(dispatched_at=now)
    if not claimed:
        return {"status": "skipped", "reason": "already_dispatched_or_missing"}

    obj = Announcement.objects.get(pk=announcement_id)
    if not is_published(obj, now):
        # Bado halijafika muda wake — rudisha claim.
        Announcement.objects.filter(pk=announcement_id).update(dispatched_at=None)
        return {"status": "skipped", "reason": "not_due"}

    try:
        new_ids = _fan_out(obj)
    except Exception:
        # Rudisha claim ili retry ianze upya (walioshapata bell wanarukwa).
        Announcement.objects.filter(pk=announcement_id).update(dispatched_at=None)
        logger.exception("announcement bell fan-out failed: id=%s", announcement_id)
        raise

    # Bell zimekamilika. Push/email — at-most-once, hazirudishi claim.
    chunks = 0
    try:
        chunks = _enqueue_channels(announcement_id, new_ids)
    except Exception:
        logger.exception(
            "announcement %s: could not enqueue push/email chunks", announcement_id,
        )

    logger.info(
        "announcement %s dispatched: %s bell, %s channel chunks",
        announcement_id, len(new_ids), chunks,
    )
    return {"status": "sent", "created": len(new_ids), "chunks": chunks}


def dispatch_pending(now=None):
    """
    Sweeper: tuma matangazo yaliyofikia muda wake (ratiba) au ambayo
    trigger ya moja kwa moja ilishindwa. Inaitwa na tasks.flush_scheduled
    (Celery beat, kila dakika).
    """
    now = now or timezone.now()
    cutoff = now - DISPATCH_WINDOW
    ids = list(
        Announcement.objects
        .filter(dispatched_at__isnull=True)
        .filter(published_q(now))
        .annotate(published_on=Coalesce("scheduled_for", "created_at"))
        .filter(published_on__gte=cutoff)
        .values_list("id", flat=True)
    )
    results = {}
    for announcement_id in ids:
        try:
            results[announcement_id] = dispatch_announcement(announcement_id)
        except Exception:
            results[announcement_id] = {"status": "error"}
    return results
