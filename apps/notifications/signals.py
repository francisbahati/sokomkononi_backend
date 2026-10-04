# ============================================================
# apps/notifications/signals.py
# Signals zinazounda notifications automatically.
# ============================================================

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification
from .services.notification import create_notification

logger = logging.getLogger(__name__)


# ============================================================
# HELPER: create notification kwa usalama
# ============================================================
def _safe_create(**kwargs):
    """
    Unda notification ndani ya transaction.on_commit ili
    tusizuie business transaction kama notification inashindwa.
    """
    def _do_create():
        try:
            create_notification(**kwargs)
        except Exception as exc:
            logger.exception(
                "[notifications] failed to create: %s", exc
            )

    transaction.on_commit(_do_create)




# ============================================================
# 3. LEAD MPYA (buyer amewasiliana)
# ============================================================
@receiver(post_save, sender="leads.Lead")
def notify_new_lead(sender, instance, created, **kwargs):
    """
    Seller anajulishwa lead mpya.
    """
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
# 4. RESERVATION CREATED
# ============================================================
@receiver(post_save, sender="transactions.Reservation")
def notify_reservation_created(sender, instance, created, **kwargs):
    """
    Seller anajulishwa mtu amehifadhi mali yake.
    """
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
# 5. BOOST ACTIVATED
# ============================================================
@receiver(post_save, sender="listings.Listing")
def notify_boost_activated(sender, instance, created, **kwargs):
    """
    Seller anajulishwa boost yake imeanza kufanya kazi.
    Trigger: boosted_until inabadilika.
    """
    if created:
        return

    if not instance.boosted_until:
        return

    # Angalia kama boosted_until ni ya hivi karibuni (dakika 5 zilizopita)
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    if instance.boosted_until <= now:
        return  # boost imeisha

    # Kama ilibadilishwa hivi karibuni
    if instance.updated_at and (now - instance.updated_at) > timedelta(minutes=5):
        return

    _safe_create(
        recipient=instance.seller,
        notification_type=Notification.NotificationType.BOOST_ACTIVATED,
        title="Boost yako imeanza kufanya kazi",
        message=(
            f'Tangazo lako "{instance.title}" litaonekana kwa '
            f"wanunuzi wengi zaidi hadi "
            f"{instance.boosted_until.strftime('%d/%m/%Y')}."
        ),
        priority=Notification.Priority.NORMAL,
        related_object_type="listings.Listing",
        related_object_id=instance.id,
        action_url=f"/mali/{instance.id}",
    )


