"""
Auto-emit notifications on events.

Every domain that wants to notify the bell calls the two helpers:

    _notify(user, TYPE, title, message, **extra)
    _notify_admin(TYPE, title, message, **extra)

The helper swallows its own exceptions so a signal failure never
breaks the caller's transaction.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification

logger = logging.getLogger(__name__)


# ── helper functions (used by every receiver) ────────────────

def _safe_create(**kwargs):
    """Create one Notification, swallow any error."""
    try:
        return Notification.objects.create(**kwargs)
    except Exception:
        logger.exception("notifications._safe_create failed: %s", kwargs)
        return None


def _notify(recipient, ntype, title, message="", **extra):
    """Notify one user."""
    if recipient is None:
        return None
    priority = extra.pop("priority", Notification.Priority.NORMAL)
    return _safe_create(
        recipient=recipient,
        audience=Notification.Audience.USER,
        notification_type=ntype,
        title=title,
        message=message,
        priority=priority,
        **extra,
    )


def _notify_admin(ntype, title, message="", **extra):
    """Notify every active staff user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    priority = extra.pop("priority", Notification.Priority.NORMAL)
    try:
        admins = User.objects.filter(is_staff=True, is_active=True)
        rows = [
            Notification(
                recipient=admin,
                audience=Notification.Audience.ADMIN,
                notification_type=ntype,
                title=title,
                message=message,
                priority=priority,
                **extra,
            )
            for admin in admins
        ]
        if rows:
            return Notification.objects.bulk_create(rows)
    except Exception:
        logger.exception("notifications._notify_admin failed")
    return None


# ── Listing events ──────────────────────────────────────────

@receiver(post_save, sender="listings.Listing")
def on_listing_saved(sender, instance, created, **kwargs):
    if not created:
        return
    seller = getattr(instance, "seller", None)
    title = getattr(instance, "title", "—")
    seller_label = (
        (getattr(seller, "name", "") or getattr(seller, "email", ""))
        if seller else "—"
    )

    # Notify admin queue
    _notify_admin(
        "LISTING_CREATED",
        f"Tangazo jipya: {title}",
        f"Na {seller_label}",
        related_object_type="listing",
        related_object_id=instance.id,
        action_url=f"/dashboard/admin/moderation?listing={instance.id}",
    )
    # Notify the seller (their listing is in the queue)
    if seller is not None:
        _notify(
            seller,
            "LISTING_CREATED",
            f"Tangazo lako linakaguliwa: {title}",
            "Litakuwa hai mara baada ya kuidhinishwa.",
            related_object_type="listing",
            related_object_id=instance.id,
            action_url="/dashboard/listings",
        )


# ── Deal room events ────────────────────────────────────────

@receiver(post_save, sender="deals.DealRoom")
def on_deal_created(sender, instance, created, **kwargs):
    if not created:
        return
    listing = getattr(instance, "listing", None)
    listing_title = getattr(listing, "title", "—") if listing else "—"

    if instance.seller_id:
        _notify(
            instance.seller,
            "TRANSACTION_CREATED",
            f"Deal mpya: {listing_title}",
            "Mnunuzi ameanza mazungumzo.",
            related_object_type="deal",
            related_object_id=instance.id,
            action_url=f"/dashboard/deals?deal={instance.id}",
        )
    if instance.buyer_id:
        _notify(
            instance.buyer,
            "TRANSACTION_CREATED",
            f"Umefungua Deal Room: {listing_title}",
            "Subiri majibu ya muuzaji.",
            related_object_type="deal",
            related_object_id=instance.id,
            action_url=f"/dashboard/buyer/deals?deal={instance.id}",
        )


# ── Messaging events ────────────────────────────────────────

@receiver(post_save, sender="messaging.Message")
def on_message_sent(sender, instance, created, **kwargs):
    if not created:
        return
    convo = getattr(instance, "conversation", None)
    if convo is None:
        return
    sender_id = instance.sender_id
    recipient = (
        convo.seller if sender_id == convo.buyer_id else convo.buyer
    )
    if recipient is None:
        return

    sender_name = "—"
    try:
        sender_name = (
            getattr(instance.sender, "name", "")
            or getattr(instance.sender, "email", "")
        )
    except Exception:
        pass

    _notify(
        recipient,
        "MESSAGE_RECEIVED",
        f"Ujumbe mpya kutoka {sender_name}",
        (instance.text or "")[:120],
        related_object_type="conversation",
        related_object_id=convo.id,
        action_url=f"/dashboard/messages?c={convo.id}",
    )


# ── Waiting list events ─────────────────────────────────────

@receiver(post_save, sender="waiting_list.WaitingListEntry")
def on_waitlist_change(sender, instance, created, **kwargs):
    if not created:
        return
    listing = getattr(instance, "listing", None)
    title = getattr(listing, "title", "—") if listing else "—"
    recipient = (
        getattr(instance, "buyer", None)
        or getattr(instance, "user", None)
    )
    if recipient is not None:
        _notify(
            recipient,
            "WAITING_LIST_JOINED",
            f"Umejiunga na waiting list: {title}",
            "Utapata taarifa nafasi ikifunguka.",
            related_object_type="listing",
            related_object_id=getattr(listing, "id", None),
            action_url="/dashboard/buyer/waiting",
        )


# ── Feedback events ────────────────────────────────────────

@receiver(post_save, sender="feedback.Feedback")
def on_feedback_created(sender, instance, created, **kwargs):
    if not created:
        return
    user = getattr(instance, "user", None)
    user_label = "—"
    try:
        user_label = (
            getattr(user, "name", "") or getattr(user, "email", "")
        )
    except Exception:
        pass
    _notify_admin(
        "VERIFICATION_REQUEST",
        f"Maoni mapya: {instance.subject}",
        f"Kutoka {user_label} ({instance.author_side})",
        related_object_type="feedback",
        related_object_id=instance.id,
        action_url="/dashboard/admin/support?view=feedback",
    )


# ── Ticket events ──────────────────────────────────────────

@receiver(post_save, sender="tickets.Ticket")
def on_ticket_created(sender, instance, created, **kwargs):
    if not created:
        return
    user = getattr(instance, "user", None)
    user_label = "—"
    try:
        user_label = (
            getattr(user, "name", "") or getattr(user, "email", "")
        )
    except Exception:
        pass
    _notify_admin(
        "VERIFICATION_REQUEST",
        f"Ticket mpya: {instance.subject}",
        f"Kutoka {user_label} — kategoria: {instance.category}",
        related_object_type="ticket",
        related_object_id=instance.id,
        action_url=f"/dashboard/admin/support?ticket={instance.id}",
    )


# ── Reservation events ─────────────────────────────────────

@receiver(post_save, sender="transactions.Reservation")
def on_reservation_created(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        txn = instance.transaction
        listing = txn.listing
        seller = txn.seller
    except Exception:
        return
    if seller is None:
        return
    _notify(
        seller,
        "RESERVATION_CREATED",
        f"Reservation mpya: {listing.title}",
        "Mnunuzi ameanza mchakato wa reservation.",
        related_object_type="transaction",
        related_object_id=txn.id,
        action_url=f"/dashboard/deals?deal={txn.deal_room_id}",
    )


# ── Verification events ────────────────────────────────────

@receiver(post_save, sender="verifications.VerificationRequest")
def on_verification_created(sender, instance, created, **kwargs):
    if not created:
        return
    user = getattr(instance, "user", None)
    user_label = "—"
    try:
        user_label = (
            getattr(user, "name", "") or getattr(user, "email", "")
        )
    except Exception:
        pass
    _notify_admin(
        "VERIFICATION_REQUEST",
        f"Ombi la uthibitisho: {instance.type}",
        f"Kutoka {user_label}",
        related_object_type="verification",
        related_object_id=instance.id,
        action_url="/dashboard/admin/verification",
    )
