"""
Banner ad creation. Reads the current Advertisement Fee config.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.listings.models import Listing

from .models import BannerAd


def _get_ad_fee_config():
    from apps.advertisement_fees.models import AdvertisementFeeConfig
    obj, _ = AdvertisementFeeConfig.objects.get_or_create(pk=1)
    return obj


@transaction.atomic
def create_banner_ad(*, listing_id, seller, payment_reference=""):
    config = _get_ad_fee_config()

    listing = Listing.objects.select_for_update().filter(pk=listing_id).first()
    if not listing:
        raise ValidationError({"listing": "Tangazo halipatikani."})
    if listing.seller_id != seller.id:
        raise ValidationError({"listing": "Huruhusiwi kutangaza tangazo ambalo si lako."})
    if listing.status != Listing.Status.AVAILABLE:
        raise ValidationError({"listing": "Tangazo lazima liwe AVAILABLE."})

    existing = BannerAd.objects.filter(
        listing=listing, active=True, expires_at__gt=timezone.now(),
    ).exists()
    if existing:
        raise ValidationError(
            {"listing": "Tangazo hili tayari lina banner inayotumika."}
        )

    now = timezone.now()
    banner = BannerAd.objects.create(
        listing=listing,
        seller=seller,
        listing_title=listing.title,
        category=getattr(listing.category, "slug", "") or "",
        location=listing.location or "",
        price=listing.price,
        seller_name=seller.name,
        amount=config.price,
        payment_reference=(payment_reference or "").strip(),
        active=True,
        expires_at=now + timedelta(days=config.days),
    )
    return banner
