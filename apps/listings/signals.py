import logging
import uuid

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


@receiver(pre_save, sender=ListingImage)
def generate_listing_image_variants(sender, instance, **kwargs):
    """
    Generate WebP variants of the (already watermarked) image.

    Registration order matters: this signal runs AFTER the watermark
    signal, so `instance.image` is the watermarked file.
    """
    if not instance.image:
        return

    update_fields = kwargs.get("update_fields")

    if instance.pk:
        if update_fields:
            if "image" not in update_fields:
                return
        else:
            if all([instance.thumb, instance.card,
                    instance.detail, instance.large]):
                return

    try:
        from .image_variants import generate_webp_variants
        variants = generate_webp_variants(instance.image)
        for name, content in variants.items():
            field = getattr(instance, name)
            field.save(
                f"{instance.listing_id}_{uuid.uuid4().hex[:8]}_{name}.webp",
                content,
                save=False,
            )
        logger.info(
            "[variants] Generated %d for image pk=%s",
            len(variants), instance.pk,
        )
    except Exception:
        logger.exception("[variants] Failed for image pk=%s", instance.pk)
