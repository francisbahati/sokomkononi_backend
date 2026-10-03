import logging

from django.core.files.base import ContentFile
from django.db.models.signals import pre_save
from django.dispatch import receiver

from apps.core.watermark import add_watermark
from .models import ListingImage

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=ListingImage)
def add_watermark_to_listing_image(sender, instance, **kwargs):
    if not instance.image:
        return

    if getattr(instance, "_watermark_applied", False):
        return

    if instance.pk:
        try:
            old = ListingImage.objects.get(pk=instance.pk)
            if old.image == instance.image:
                return
        except ListingImage.DoesNotExist:
            pass

    try:
        watermarked = add_watermark(instance.image)
        original_name = instance.image.name
        instance.image.save(
            original_name,
            ContentFile(watermarked.read()),
            save=False,
        )
        instance._watermark_applied = True
        logger.info("[watermark] Applied to %s", original_name)
    except Exception as exc:
        logger.exception(
            "[watermark] Failed for %s: %s",
            instance.image.name, exc,
        )