import logging

from django.conf import settings
from django.core.mail import send_mail
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
        return
    try:
        send_mail(
            subject=f"[Contact] {instance.subject[:80]}",
            message=(
                f"From: {instance.name} <{instance.email}>\n"
                f"Phone: {instance.phone or '—'}\n\n"
                f"{instance.message}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("contact admin notify failed for %s", instance.pk)
