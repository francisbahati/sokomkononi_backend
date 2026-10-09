from rest_framework.exceptions import PermissionDenied
from django.utils import timezone

from ..models import Notification


# ============================================================
# NOTIFICATION TYPE → (channel, category) MAPPING
# ============================================================
#
# Kila notification_type inahusiana na channel + category.
# `_should_send_via_channel()` inatumia hii kupata prefs field
# inayofaa (mfano `email_deals`, `push_deals`).
#
# NOTE (Chaguo B): Mapping hii HAITUMIKI kuzuia in-app notifications.
# Inatumika TU kwenye send_notification_via_channels() — kwa
# email/SMS/push services.
#
_NOTIFICATION_TYPE_MAP = {
    # ── Listings — deals ──────────────────────────────────
    "LISTING_CREATED":    ("email", "deals"),
    "LISTING_APPROVED":   ("email", "deals"),
    "LISTING_REJECTED":   ("email", "deals"),
    "LISTING_DELETED":    ("email", "deals"),
    "LISTING_RESTORED":   ("email", "deals"),

    # ── Deals / Offers — deals ────────────────────────────
    "NEW_OFFER":           ("push",  "deals"),
    "OFFER_COUNTERED":     ("push",  "deals"),
    "OFFER_ACCEPTED":      ("push",  "deals"),

    # ── Transactions — deals ──────────────────────────────
    "TRANSACTION_CREATED":   ("email", "deals"),
    "TRANSACTION_COMPLETED": ("email", "deals"),
    "TRANSACTION_CANCELLED": ("email", "deals"),

    # ── Reservations — deals ──────────────────────────────
    "RESERVATION_CREATED":  ("email", "deals"),
    "RESERVATION_PAID":     ("email", "deals"),
    "RESERVATION_EXPIRING": ("push",  "deals"),
    "RESERVATION_EXPIRED":  ("email", "deals"),

    # ── Inspection / Buyer decision — deals ───────────────
    "INSPECTION_STARTED":   ("email", "deals"),
    "INSPECTION_COMPLETED": ("email", "deals"),
    "BUYER_DECISION":       ("email", "deals"),

    # ── Payment proof — deals ─────────────────────────────
    "PAYMENT_PROOF_UPLOADED": ("push",  "deals"),
    "PAYMENT_CONFIRMED":      ("email", "deals"),

    # ── Waiting list — deals ──────────────────────────────
    "WAITING_LIST_JOINED":    ("email", "deals"),
    "WAITING_LIST_AVAILABLE": ("push",  "deals"),

    # ── Boost — promotions ────────────────────────────────
    "BOOST_ACTIVATED": ("email", "promotions"),

    # ── System notifications — always send ────────────────
    "ACCOUNT_DELETED":  (None, None),
    "ACCOUNT_RESTORED": (None, None),
    "GENERAL":          (None, None),
}


def _should_send_via_channel(recipient, notification_type, channel):
    """
    Angalia kama mtumiaji amezima channel fulani (email/sms/push)
    kwa notification_type fulani.

    Chaguo B: Function hii HAITUMIKI kwenye create_notification().
    Inatumika TU kwenye send_notification_via_channels() baadaye.

    Args:
        recipient: User
        notification_type: str (mfano "NEW_OFFER")
        channel: "email" | "sms" | "push"

    Returns:
        True — tuma
        False — mtumiaji amezima channel hii kwa category hii
    """
    try:
        prefs = recipient.notification_preferences
    except Exception:
        return True  # Hakuna prefs — tuma

    nt = str(notification_type or "").strip().upper()
    if not nt:
        return True

    if nt not in _NOTIFICATION_TYPE_MAP:
        return True  # Haijulikani — tuma

    mapped_channel, category = _NOTIFICATION_TYPE_MAP[nt]

    # System notification — tuma kila wakati
    if mapped_channel is None or category is None:
        return True

    # Kama channel iliyotolewa ni tofauti na mapping, tuma
    # (mfano: unaweza kutaka kutuma via email hata kama mapping ni push)
    if channel != mapped_channel:
        # Angalia prefs field kwa channel iliyotolewa
        field = f"{channel}_{category}"
    else:
        field = f"{channel}_{category}"

    if not hasattr(prefs, field):
        return True

    return bool(getattr(prefs, field))


def create_notification(
    *,
    recipient,
    notification_type,
    title,
    message,
    priority=Notification.Priority.NORMAL,
    audience=Notification.Audience.USER,
    related_object_type="",
    related_object_id=None,
    action_url="",
):
    """
    Create a notification (in-app, DB record).

    Chaguo B: Hii inaunda DB record KILA WAKATI bila kuzingatia
    prefs za mtumiaji. Mtumiaji anaona kwenye bell icon.

    Prefs za mtumiaji zinaathiri TU email/SMS/push — ambazo
    zinatumwa kupitia `send_notification_via_channels()`.

    Callers that run inside an atomic block should invoke this via
    transaction.on_commit() to avoid coupling the notification write
    to the business transaction.
    """
    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=priority,
        audience=audience,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        action_url=action_url,
    )


# ============================================================
# OPTIONAL — SEND VIA CHANNELS (email/SMS/push)
# ============================================================
# Hii ni kwa siku zijazo ukiongeza email/SMS/push services.
# Kwa sasa ina-log tu (hakuna kutuma).
#
# Matumizi:
#   create_notification(...)                       # in-app, kila wakati
#   send_notification_via_channels(recipient, ...) # email/SMS/push kwa prefs
#
def send_notification_via_channels(   # noqa: F811  (documented stub)
    # NOTE: email/SMS/push delivery is not yet implemented.
    # This function currently returns False for every channel.
    # Wire it to real providers before relying on it.

    *,
    recipient,
    notification_type,
    title,
    message,
    channels=("email", "sms", "push"),
    **kwargs,
):
    """
    Tuma notification kupitia channels mbalimbali, ukizingatia
    prefs za mtumiaji.

    Kwa sasa hii ni **stub** — ina-log tu. Ukiongeza email/SMS/push
    services, badilisha `_send_via_channel()` hapa chini.

    Args:
        channels: Tuple ya channels za kujaribu. Default: zote tatu.

    Returns:
        dict { channel: bool } — True kama ilitumwa, False kama ilirukwa.
    """
    results = {}

    for channel in channels:
        if not _should_send_via_channel(recipient, notification_type, channel):
            results[channel] = False
            continue

        sent = _send_via_channel(
            channel=channel,
            recipient=recipient,
            title=title,
            message=message,
            **kwargs,
        )
        results[channel] = sent

    return results


def _send_via_channel(*, channel, recipient, title, message, **kwargs):
    """
    Tuma notification via channel fulani.

    Chaguo B: Hii ni stub kwa sasa — ina-log tu. Ukiongeza services,
    badilisha code hapa.
    """
    import logging
    logger = logging.getLogger(__name__)

    if channel == "email":
        # TODO: integrate email service
        # from .email_service import send_email
        # send_email(recipient.email, title, message)
        logger.info(
            "[notif:email] Would send to %s: %s — %s",
            recipient.email, title, message,
        )
        return True

    if channel == "sms":
        # TODO: integrate SMS service (FimiPay/Beem)
        # from .sms_service import send_sms
        # send_sms(recipient.phone, message)
        if not recipient.phone:
            return False
        logger.info(
            "[notif:sms] Would send to %s: %s",
            recipient.phone, title,
        )
        return True

    if channel == "push":
        # TODO: integrate push service (Firebase/OneSignal)
        # from .push_service import send_push
        # send_push(recipient.id, title, message)
        logger.info(
            "[notif:push] Would send to user %s: %s — %s",
            recipient.id, title, message,
        )
        return True

    return False


def mark_notification_as_read(*, notification, user):
    if notification.recipient_id != user.id and not user.is_staff:
        raise PermissionDenied(
            "Huruhusiwi kubadilisha arifa ya mtumiaji mwingine."
        )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(
            update_fields=["is_read", "read_at", "updated_at"],
        )

    return notification


def mark_all_notifications_as_read(*, user):
    now = timezone.now()
    return (
        Notification.objects
        .filter(recipient=user, is_read=False)
        .update(is_read=True, read_at=now, updated_at=now)
    )


def get_unread_notification_count(*, user):
    return Notification.objects.filter(
        recipient=user, is_read=False,
    ).count()


# ============================================================
# ADMIN NOTIFICATIONS — broadcast kwa admins wote
# ============================================================

def create_notification_for_admins(
    *,
    notification_type,
    title,
    message,
    priority=Notification.Priority.NORMAL,
    related_object_type="",
    related_object_id=None,
    action_url="",
    exclude_user_id=None,
):
    """
    Tuma notification kwa admins wote (is_staff=True).

    Admin notifications HAZIATHIRIWI na prefs za mtumiaji —
    admin anaona kila kitu.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    admins = User.objects.filter(
        is_staff=True,
        is_active=True,
    )

    if exclude_user_id is not None:
        admins = admins.exclude(pk=exclude_user_id)

    admins = admins.distinct()

    notifications = [
        Notification(
            recipient=admin,
            notification_type=notification_type,
            title=title,
            message=message,
            priority=priority,
            audience=Notification.Audience.ADMIN,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
            action_url=action_url,
        )
        for admin in admins
    ]

    if not notifications:
        return []

    return Notification.objects.bulk_create(notifications)