# apps/accounts/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import (
    NotificationPreference,
    User,
    UserPreferences,
)


@receiver(post_save, sender=User)
def create_user_related_models(sender, instance, created, **kwargs):
    """
    Kila user mpya anapoundwa, unda:
      - UserPreferences (prefs za jumla)
      - NotificationPreference (mipangilio ya taarifa)
    """
    if not created:
        return
    try:
        UserPreferences.objects.get_or_create(user=instance)
        NotificationPreference.objects.get_or_create(user=instance)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to create preferences for user %s", instance.pk,
        )