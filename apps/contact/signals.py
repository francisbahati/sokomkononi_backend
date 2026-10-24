# signals.py
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ContactMessage

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ContactMessage)
def notify_admin_of_contact(sender, instance, created, **kwargs):
    if not created:
        return

    admin_email = getattr(settings, "ADMIN_EMAIL", "")
    if not admin_email:
        logger.warning("ADMIN_EMAIL haijawekwa kwenye settings; barua pepe haijatumwa.")
        return

    subject = f"[Contact] {instance.subject[:80]}"
    body = (
        f"From: {instance.name} <{instance.email}>\n"
        f"Phone: {instance.phone or '—'}\n"
        f"Subject: {instance.subject}\n"
        f"Tarehe: {instance.created_at:%Y-%m-%d %H:%M}\n\n"
        f"Ujumbe:\n{instance.message}\n\n"
        f"—\n"
        f"Unaweza kujibu barua pepe hii moja kwa moja; itakwenda kwa {instance.email}."
    )

    try:
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[admin_email],
            reply_to=[instance.email],  # <--- Muhimu: reply inaenda kwa mteja
        )
        msg.send(fail_silently=False)
        logger.info(
            "Contact notification sent to %s (reply-to: %s) for message #%s",
            admin_email, instance.email, instance.pk,
        )
    except Exception:
        logger.exception(
            "contact admin notify failed for message #%s (to=%s)",
            instance.pk, admin_email,
        )