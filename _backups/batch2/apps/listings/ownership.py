"""
Shared listing lookup helpers.

Every endpoint that resolves a listing from a URL must respect the
same ownership rule:

    - Anonymous            → LIVE / RESERVED / SOLD only
    - Authenticated owner  → any status (including PENDING_PAYMENT,
                             DRAFT, REJECTED) + soft-deleted
    - Staff / superuser    → everything, including soft-deleted
"""
from django.db.models import Q

from .models import Listing


PUBLIC_STATUSES = (
    Listing.Status.LIVE,
    Listing.Status.RESERVED,
    Listing.Status.SOLD,
)


def listings_visible_to(user):
    """Queryset of listings visible to `user` for READ operations."""
    base = Listing.all_objects.all()

    if not user or not user.is_authenticated:
        return base.filter(
            is_deleted=False,
            status__in=PUBLIC_STATUSES,
        )

    if user.is_staff or user.is_superuser:
        return base

    # Owners see their own listings in any status, even soft-deleted,
    # so a seller can always pay for / inspect their own drafts.
    return base.filter(
        Q(seller=user)
        | Q(is_deleted=False, status__in=PUBLIC_STATUSES)
    ).distinct()


def get_owned_or_public_listing(user, listing_id, *, include_deleted_for_owner=True):
    """
    Return a single Listing for the given id, or None.

    Owners get their own soft-deleted listings too (so they can pay,
    restore, or view the fee). Everyone else gets only what's public.
    """
    base = Listing.all_objects.all()

    if user and user.is_authenticated:
        if user.is_staff or user.is_superuser:
            return base.filter(pk=listing_id).first()

        owner_q = Q(seller=user)
        if not include_deleted_for_owner:
            owner_q &= Q(is_deleted=False)

        return base.filter(
            Q(pk=listing_id) & (
                owner_q
                | Q(is_deleted=False, status__in=PUBLIC_STATUSES)
            )
        ).first()

    return base.filter(
        pk=listing_id,
        is_deleted=False,
        status__in=PUBLIC_STATUSES,
    ).first()
