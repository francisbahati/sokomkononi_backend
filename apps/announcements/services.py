# ============================================================
# apps/announcements/services.py   (FILE MPYA)
#
# - Kanuni ya "imetumwa" (is_published / published_q / sync_due)
# - Utoaji wa arifa (deliver): tangazo likitumwa, watumiaji wanapata
#   arifa. Njia inayotumika:
#     1. `apps.notifications.services.send_announcement(announcement)`
#        kama ipo (ya mradi wako — push/SMS/email kulingana na tasks za
#        zamani), AU
#     2. fallback: Notification ya ndani (bell) kwa kila mtumiaji hai.
#   Njia moja tu hutumika kwa kila tangazo, kwa hiyo hakuna nakala.
#
# Usalama wa kutuma mara moja tu:
#  - `dispatched_at` inadaiwa (claim) kwa UPDATE ya atomic; mtu wa
#    kwanza tu ndiye anayeendelea.
#  - send_announcement ikishindwa: claim INABAKI (at-most-once, kama
#    flush_scheduled ya zamani) — hatujui ilituma kwa nani kabla ya kuanguka.
#  - Fallback ya bell ikishindwa: claim inarudishwa; retry inaruka
#    walioshapata, kwa hiyo hakuna nakala.
# ============================================================
import logging
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Announcement

logger = logging.getLogger(__name__)

_warned_no_sender = False

RELATED_TYPE = "announcement"
BATCH_SIZE = 500

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
# FAN-OUT
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


def _fan_out(obj):
    """Unda Notification kwa kila mtumiaji hai. Inarudisha idadi mpya."""
    from apps.notifications.models import Notification

    User = get_user_model()
    lang_field = _lang_field(User)
    fields = ["id"] + ([lang_field] if lang_field else [])

    priority = (
        Notification.Priority.HIGH
        if obj.type == Announcement.Type.MAINTENANCE
        else Notification.Priority.NORMAL
    )

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
        if rows:
            Notification.objects.bulk_create(rows, batch_size=BATCH_SIZE)
        return len(rows)

    created = 0
    batch = []
    users = User.objects.filter(is_active=True).order_by("id").values_list(*fields)
    for row in users.iterator(chunk_size=2000):
        batch.append(row)
        if len(batch) >= BATCH_SIZE:
            created += flush(batch)
            batch = []
    if batch:
        created += flush(batch)
    return created


def _external_sender():
    """`send_announcement` ya mradi (apps.notifications.services), au None."""
    global _warned_no_sender
    try:
        from apps.notifications.services import send_announcement
        return send_announcement
    except ImportError:
        if not _warned_no_sender:
            logger.warning(
                "apps.notifications.services.send_announcement haipatikani — "
                "natumia fallback ya bell (in-app) kwa matangazo.",
                exc_info=True,
            )
            _warned_no_sender = True
        return None


def dispatch_announcement(announcement_id):
    """
    Tuma arifa za tangazo kwa watumiaji — mara moja tu.
    Inarudisha {"status": "sent"|"skipped"|"error", ...}.
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

    sender = _external_sender()
    if sender is not None:
        try:
            sender(obj)
        except Exception:
            # At-most-once: claim inabaki (angalia maelezo juu ya faili).
            logger.exception(
                "send_announcement failed: announcement id=%s", announcement_id,
            )
            return {"status": "error", "via": "send_announcement"}
        return {"status": "sent", "via": "send_announcement"}

    try:
        created = _fan_out(obj)
    except Exception:
        Announcement.objects.filter(pk=announcement_id).update(dispatched_at=None)
        logger.exception("announcement fan-out failed: id=%s", announcement_id)
        raise
    logger.info("announcement %s dispatched in-app: %s", announcement_id, created)
    return {"status": "sent", "via": "in_app", "created": created}


def dispatch_pending(now=None):
    """
    Sweeper: tuma arifa za matangazo yaliyofikia muda wake (ratiba) au
    ambayo trigger ya moja kwa moja ilishindwa. Inaitwa na
    tasks.flush_scheduled (Celery beat, kila dakika).
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
            results[announcement_id] = {"status": "error", "via": "in_app"}
    return results
