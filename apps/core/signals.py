"""
Global signals for the core app.

Registered in apps.CoreConfig.ready().

Deletes the underlying storage object whenever a model instance
that owns a FileField / ImageField is hard-deleted.
"""

import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.listings.models import ListingImage
from apps.transactions.models import Transaction


logger = logging.getLogger(__name__)


def _delete_file(field_file):
    """
    Best-effort storage delete. Never raises.
    """
    if not field_file:
        return

    try:
        field_file.delete(save=False)
    except Exception:
        logger.exception(
            "Failed to delete storage object %s", field_file.name
        )


@receiver(post_delete, sender=ListingImage)
def delete_listing_image_file(sender, instance, **kwargs):
    """Remove the underlying image file when a ListingImage is deleted."""
    _delete_file(instance.image)


@receiver(post_delete, sender=Transaction)
def delete_transaction_proof_file(sender, instance, **kwargs):
    """Remove the final payment proof when a Transaction is deleted."""
    _delete_file(instance.final_payment_proof)