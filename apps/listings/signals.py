import logging
import uuid

from django.core.files.base import ContentFile
from django.db.models.signals import pre_save
from django.dispatch import receiver

from apps.core.watermark import add_watermark

from .models import ListingImage

logger = logging.getLogger(__name__)


def _apply_watermark(instance):
    """Ongeza watermark kwenye picha mpya ya listing."""
    if not instance.image:
        return

    # Update mode — angalia kama picha imebadilika
    if instance.pk:
        try:
            old = ListingImage.objects.only("image").get(pk=instance.pk)
            if old.image.name == instance.image.name:
                return
        except ListingImage.DoesNotExist:
            pass

    try:
        w = add_watermark(instance.image, position="bottom-right")
        w.seek(0)

        # Fallback name kama `instance.image.name` ni None
        name = instance.image.name or (
            f"listing_{instance.listing_id}_{uuid.uuid4().hex[:8]}.jpg"
        )

        instance.image.save(
            name,
            ContentFile(w.read()),
            save=False,
        )
        logger.info("[watermark] applied to %s", name)
    except Exception:
        logger.exception(
            "[watermark] failed for %s", instance.image.name or "(no name)"
        )


def _generate_variants(instance):
    """Tengeneza WebP variants kutoka picha yenye watermark."""
    if not instance.image:
        return

    uf = getattr(instance, "_update_fields_ctx", None)

    if instance.pk:
        if uf and "image" not in uf:
            return
        if not uf and all([
            instance.thumb,
            instance.card,
            instance.detail,
            instance.large,
        ]):
            return

    try:
        from .image_variants import generate_webp_variants
        for name, content in generate_webp_variants(instance.image).items():
            getattr(instance, name).save(
                f"{instance.listing_id}_{uuid.uuid4().hex[:8]}_{name}.webp",
                content,
                save=False,
            )
    except Exception:
        logger.exception("[variants] failed for image pk=%s", instance.pk)


@receiver(pre_save, sender=ListingImage)
def process_listing_image(sender, instance, **kwargs):
    """
    Signal inayofanya kazi kwa mpangilio:
      1. Ongeza watermark kwenye picha ya asili.
      2. Tengeneza WebP variants kutoka picha yenye watermark.
    """
    _apply_watermark(instance)
    _generate_variants(instance)