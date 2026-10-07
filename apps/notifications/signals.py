# ============================================================
# apps/notifications/signals.py
# Signals zinazounda notifications automatically.
# ============================================================

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Notification
from .services.notification import (
    create_notification,
    create_notification_for_admins,
)

logger = logging.getLogger(__name__)

# ============================================================
# HELPERS
# ============================================================
def _safe_create(**kwargs):
    """Unda notification kwa user ndani ya on_commit."""
    def _do_create():
        try:
            create_notification(**kwargs)
        except Exception as exc:
            logger.exception("[notifications] failed to create: %s", exc)

    transaction.on_commit(_do_create)

def _safe_create_for_admins(**kwargs):
    """Unda notification kwa admins wote ndani ya on_commit."""
    def _do_create():
        try:
            create_notification_for_admins(**kwargs)
        except Exception as exc:
            logger.exception(
                "[notifications] failed to create for admins: %s", exc
            )

    transaction.on_commit(_do_create)

# ============================================================
# 1. USER — mtumiaji mpya amejisajili
# ============================================================
@receiver(post_save, sender="accounts.User")
def notify_admin_new_user(sender, instance, created, **kwargs):
    """Admin anajulishwa mtumiaji mpya amejisajili."""
    if not created:
        return
    if instance.is_staff:
        return  # ruka admins wenyewe

    _safe_create_for_admins(
        notification_type=Notification.NotificationType.GENERAL,
        title="Mtumiaji mpya amejisajili",
        message=(
            f'{instance.name or "Mtumiaji"} ({instance.email}) '
            f"amejisajili kwenye SokoMkononi."
        ),
        priority=Notification.Priority.NORMAL,
        related_object_type="accounts.User",
        related_object_id=instance.id,
        action_url=f"{_admin_path()}/users",
    )

# ============================================================
# 2. USER — amefutwa
# ============================================================
@receiver(pre_save, sender="accounts.User")
def notify_admin_user_deleted(sender, instance, **kwargs):
    """Admin anajulishwa mtumiaji amefutwa."""
    if not instance.pk:
        return

    try:
        old = sender.all_objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    # Angalia kama is_deleted ilibadilika kutoka False → True
    if not old.is_deleted and instance.is_deleted:
        # Kama ni admin mwenyewe, usitume
        if instance.is_staff:
            return

        _safe_create_for_admins(
            notification_type=Notification.NotificationType.ACCOUNT_DELETED,
            title="Mtumiaji amefutwa",
            message=(
                f'{instance.name or "Mtumiaji"} ({instance.email}) '
                f"amefuta akaunti yake.\n\n"
                f"Sababu: {instance.deletion_reason or 'Hakuna sababu'}"
            ),
            priority=Notification.Priority.HIGH,
            related_object_type="accounts.User",
            related_object_id=instance.id,
            action_url=f"{_admin_path()}/trash",
            exclude_user_id=instance.id,
        )

# ============================================================
# 3. LISTING — mpya imewekwa
# ============================================================
@receiver(post_save, sender="listings.Listing")
def notify_admin_new_listing(sender, instance, created, **kwargs):
    """Admin anajulishwa listing mpya imewekwa."""
    if not created:
        return

    seller_name = (
        instance.seller.name if instance.seller else "Muuzaji"
    )
    category_name = (
        instance.category.name if instance.category else "—"
    )

    _safe_create_for_admins(
        notification_type=Notification.NotificationType.LISTING_CREATED,
        title="Tangazo jipya limewekwa",
        message=(
            f'{seller_name} ameweka tangazo jipya: "{instance.title}"\n'
            f"Kategoria: {category_name}\n"
            f"Bei: TZS {instance.price:,}\n"
            f"Mahali: {instance.location}"
        ),
        priority=Notification.Priority.NORMAL,
        related_object_type="listings.Listing",
        related_object_id=instance.id,
        action_url=f"{_admin_path()}/moderation",
    )

# ============================================================
# 4. LISTING — imefutwa (soft delete)
# ============================================================
@receiver(pre_save, sender="listings.Listing")
def notify_admin_listing_deleted(sender, instance, **kwargs):
    """Admin anajulishwa listing imefutwa."""
    if not instance.pk:
        return

    try:
        old = sender.all_objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    # Angalia kama is_deleted ilibadilika False → True
    if not old.is_deleted and instance.is_deleted:
        seller_name = (
            instance.seller.name if instance.seller else "Muuzaji"
        )

        _safe_create_for_admins(
            notification_type=Notification.NotificationType.LISTING_DELETED,
            title="Tangazo limefutwa",
            message=(
                f'{seller_name} amefuta tangazo "{instance.title}".\n\n'
                f"Sababu: {instance.deletion_reason or 'Hakuna sababu'}"
            ),
            priority=Notification.Priority.NORMAL,
            related_object_type="listings.Listing",
            related_object_id=instance.id,
            action_url=f"{_admin_path()}/trash",
        )

# ============================================================
# 5. LEAD MPYA (buyer amewasiliana)
# ============================================================
@receiver(post_save, sender="leads.Lead")
def notify_new_lead(sender, instance, created, **kwargs):
    """Seller anajulishwa lead mpya."""
    if not created:
        return

    if not instance.listing_id:
        return

    try:
        listing = instance.listing
        seller = listing.seller
        buyer_name = (
            getattr(instance, "buyer_name", "")
            or getattr(instance, "name", "")
            or "Mnunuzi"
        )

        _safe_create(
            recipient=seller,
            notification_type=Notification.NotificationType.GENERAL,
            title="Ujumbe mpya kutoka kwa mnunuzi",
            message=(
                f'{buyer_name} ana nia ya mali yako '
                f'"{listing.title}". Jibu haraka.'
            ),
            priority=Notification.Priority.HIGH,
            related_object_type="leads.Lead",
            related_object_id=instance.id,
            action_url=f"/dashboard/seller/leads",
        )
    except Exception as exc:
        logger.exception("[notifications] lead signal failed: %s", exc)

# ============================================================
# 6. RESERVATION CREATED
# ============================================================
@receiver(post_save, sender="transactions.Reservation")
def notify_reservation_created(sender, instance, created, **kwargs):
    """Seller anajulishwa mtu amehifadhi mali yake."""
    if not created:
        return

    try:
        transaction_obj = instance.transaction
        listing = transaction_obj.listing
        seller = listing.seller

        _safe_create(
            recipient=seller,
            notification_type=Notification.NotificationType.RESERVATION_CREATED,
            title="Mali yako imehifadhiwa",
            message=(
                f'Mtu amehifadhi "{listing.title}". '
                f"Reservation itaisha baada ya muda uliowekwa."
            ),
            priority=Notification.Priority.HIGH,
            related_object_type="transactions.Reservation",
            related_object_id=instance.id,
            action_url=f"/dashboard/seller/transactions/{transaction_obj.id}",
        )
    except Exception as exc:
        logger.exception("[notifications] reservation signal failed: %s", exc)

# ============================================================
# 8. VERIFICATION REQUEST — mpya imewasilishwa (admin)
# ============================================================
@receiver(post_save, sender="verifications.VerificationRequest")
def notify_admin_new_verification(sender, instance, created, **kwargs):
    """Admin anajulishwa verification request mpya."""
    if not created:
        return

    # Ruka kama ni staff mwenyewe
    if instance.user and instance.user.is_staff:
        return

    user_name = instance.user_name or (
        instance.user.name if instance.user else "Mtumiaji"
    )
    user_email = instance.user_email or (
        instance.user.email if instance.user else "—"
    )

    # Type labels kwa lugha rahisi
    TYPE_LABELS = {
        "SELLER": "Muuzaji",
        "BUYER": "Mnunuzi",
        "PROPERTY": "Mali (Nyumba/Jengo)",
        "VEHICLE": "Gari",
        "BUSINESS": "Biashara",
    }
    type_label = TYPE_LABELS.get(instance.type, instance.type)

    _safe_create_for_admins(
        notification_type=Notification.NotificationType.GENERAL,
        title="Ombi jipya la uthibitisho",
        message=(
            f'{user_name} ({user_email}) amewasilisha ombi la '
            f"uthibitisho wa {type_label}.\n\n"
            f"Mada: {instance.subject or '—'}\n"
            f"Angalia na uidhinishe."
        ),
        priority=Notification.Priority.HIGH,
        related_object_type="verifications.VerificationRequest",
        related_object_id=instance.id,
        action_url=f"{_admin_path()}/verification",
        exclude_user_id=instance.user_id,
    )

# ============================================================
# 9. VERIFICATION REQUEST — imeidhinishwa / imekataliwa (user)
# ============================================================
@receiver(pre_save, sender="verifications.VerificationRequest")
def notify_verification_status_changed(sender, instance, **kwargs):
    """Mtumiaji anajulishwa verification yake imeidhinishwa au imekataliwa."""
    if not instance.pk:
        return

    try:
        old = sender.all_objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    # Angalia kama status ilibadilika kutoka PENDING
    if old.status != "PENDING" or instance.status == "PENDING":
        return

    if not instance.user:
        return

    if instance.status == "APPROVED":
        _safe_create(
            recipient=instance.user,
            notification_type=Notification.NotificationType.GENERAL,
            title="Uthibitisho wako umeidhinishwa",
            message=(
                f'Ombi lako la uthibitisho wa {instance.get_type_display()} '
                f"limeidhinishwa. Sasa unaweza kufurahia huduma zote za "
                f"SokoMkononi."
            ),
            priority=Notification.Priority.HIGH,
            related_object_type="verifications.VerificationRequest",
            related_object_id=instance.id,
            action_url="/dashboard/verification",
        )
    elif instance.status == "REJECTED":
        reason = instance.rejection_reason or "Hakuna sababu iliyotolewa."

        _safe_create(
            recipient=instance.user,
            notification_type=Notification.NotificationType.GENERAL,
            title="Uthibitisho wako umekataliwa",
            message=(
                f'Ombi lako la uthibitisho wa {instance.get_type_display()} '
                f"limekataliwa.\n\n"
                f"Sababu: {reason}\n\n"
                f"Unaweza kuwasilisha tena baada ya kurekebisha."
            ),
            priority=Notification.Priority.HIGH,
            related_object_type="verifications.VerificationRequest",
            related_object_id=instance.id,
            action_url="/dashboard/verification",
        )

def _admin_path():
    """Local alias for the shared admin-path helper."""
    from apps.core.admin_path import get_admin_path
    return get_admin_path()
