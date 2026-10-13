from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.listings.models import Listing

from ..models import WaitingListEntry


def get_next_waiting_position(listing):
    last_entry = (
        WaitingListEntry.objects
        .filter(listing=listing, status=WaitingListEntry.Status.WAITING)
        .order_by("-position")
        .first()
    )
    return 1 if not last_entry else last_entry.position + 1


@transaction.atomic
def join_waiting_list(*, listing, buyer):
    if not buyer.is_authenticated:
        raise ValidationError("Lazima uwe umeingia kwenye akaunti.")
    if not buyer.is_active:
        raise ValidationError("Akaunti yako haijawezeshwa.")
    if not buyer.is_verified:
        raise ValidationError(
            "Akaunti yako lazima iwe imethibitishwa."
        )

    listing = Listing.objects.select_for_update().get(pk=listing.pk)

    if listing.seller_id == buyer.id:
        raise ValidationError(
            "Huwezi kujiunga kwenye waiting list ya tangazo lako."
        )
    if listing.status != Listing.Status.RESERVED:
        raise ValidationError(
            "Waiting list inapatikana kwa tangazo lililo RESERVED pekee."
        )

    existing = WaitingListEntry.objects.filter(
        listing=listing, buyer=buyer,
    ).first()

    if existing:
        if existing.status in [
            WaitingListEntry.Status.WAITING,
            WaitingListEntry.Status.NOTIFIED,
        ]:
            raise ValidationError(
                "Tayari uko kwenye waiting list ya tangazo hili."
            )

        # Re-join: reuse the row.
        existing.status = WaitingListEntry.Status.WAITING
        existing.position = get_next_waiting_position(listing)
        existing.notified_at = None
        existing.respond_by = None
        existing.save(update_fields=[
            "status", "position", "notified_at", "respond_by", "updated_at",
        ])
        return existing

    position = get_next_waiting_position(listing)

    return WaitingListEntry.objects.create(
        listing=listing,
        buyer=buyer,
        status=WaitingListEntry.Status.WAITING,
        position=position,
    )


@transaction.atomic
def leave_waiting_list(*, entry, buyer):
    if entry.buyer_id != buyer.id and not buyer.is_staff:
        raise ValidationError(
            "Huruhusiwi kuondoa entry hii ya waiting list."
        )

    if entry.status in [
        WaitingListEntry.Status.CANCELLED,
        WaitingListEntry.Status.FULFILLED,
    ]:
        raise ValidationError("Entry hii tayari imefungwa.")

    listing_id = entry.listing_id

    entry.status = WaitingListEntry.Status.CANCELLED
    entry.save(update_fields=["status", "updated_at"])

    reorder_waiting_list(listing_id=listing_id)


@transaction.atomic
def reorder_waiting_list(*, listing_id):
    entries = list(
        WaitingListEntry.objects
        .select_for_update()
        .filter(
            listing_id=listing_id,
            status__in=[
                WaitingListEntry.Status.WAITING,
                WaitingListEntry.Status.NOTIFIED,
            ],
        )
        .order_by("joined_at", "id")
    )

    for position, entry in enumerate(entries, start=1):
        if entry.position != position:
            entry.position = position
            entry.save(update_fields=["position", "updated_at"])


@transaction.atomic
def fulfil_waiting_entry(*, entry):
    entry = WaitingListEntry.objects.select_for_update().get(pk=entry.pk)

    if entry.status == WaitingListEntry.Status.FULFILLED:
        return entry

    entry.status = WaitingListEntry.Status.FULFILLED
    entry.save(update_fields=["status", "updated_at"])
    return entry

@transaction.atomic
def claim_waitlist_entry(*, entry, user):
    entry = (WaitingListEntry.objects.select_for_update()
             .select_related("listing", "buyer").get(pk=entry.pk))
    if entry.buyer_id != user.id: raise ValidationError("Huna ruhusa.")
    if entry.status != WaitingListEntry.Status.NOTIFIED:
        raise ValidationError("Nafasi yako bado haijafunguliwa.")
    if entry.respond_by and entry.respond_by <= timezone.now():
        raise ValidationError("Muda wa kuchukua nafasi umepita.")
    if entry.listing.status != Listing.Status.LIVE:
        raise ValidationError("Tangazo halipo tena.")
    from apps.deals.models import DealRoom
    from apps.transactions.models import Transaction
    from apps.transactions.services.reservation import create_reservation
    dr = DealRoom.objects.filter(listing=entry.listing, buyer=user).order_by("-created_at").first()
    if not dr: raise ValidationError("Anzisha Deal Room kwanza.")
    txn, _ = Transaction.objects.get_or_create(deal_room=dr, defaults={
        "listing": entry.listing, "buyer": user, "seller": entry.listing.seller,
        "agreed_price": dr.agreed_price or entry.listing.price,
        "status": Transaction.Status.RESERVATION_PENDING})
    res = create_reservation(transaction=txn, user=user, duration_hours=24)
    entry.status = WaitingListEntry.Status.FULFILLED
    entry.save(update_fields=["status", "updated_at"])
    return {"entry": entry, "transaction": txn, "reservation": res}
