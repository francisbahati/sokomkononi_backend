"""
Auto-create/update a Lead when a DealRoom is created or updated.
Called from apps.deals.services (or via a signal).
"""

from apps.deals.models import DealRoom

from ..models import Lead


def upsert_lead_from_deal_room(deal_room: DealRoom):
    """
    Create or update the Lead corresponding to a DealRoom.
    Buyer, seller, listing and initial message come from the room.
    """
    if not deal_room or not deal_room.pk:
        return None

    listing = deal_room.listing
    buyer = deal_room.buyer
    seller = deal_room.seller

    initial_message = ""
    last_message = (
        deal_room.offers
        .order_by("-created_at")
        .values_list("message", flat=True)
        .first()
    )
    if last_message:
        initial_message = last_message

    lead, created = Lead.objects.get_or_create(
        listing=listing,
        buyer=buyer,
        defaults={
            "seller": seller,
            "buyer_name": buyer.name,
            "message": initial_message,
            "source": Lead.Source.DEAL,
            "status": Lead.Status.NEW,
            "deal_room": deal_room,
            "message_count": 1,
        },
    )

    if not created:
        # Update message + count on subsequent activity
        Lead.objects.filter(pk=lead.pk).update(
            message=initial_message or lead.message,
            message_count=Lead.objects.get(pk=lead.pk).message_count + 1,
        )
        lead.refresh_from_db()

    return lead