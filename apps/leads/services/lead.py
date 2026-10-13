from django.db import models
from django.utils import timezone
from ..models import Lead

def upsert_lead_from_deal_room(deal_room):
    if not deal_room or not deal_room.pk: return None
    listing, buyer, seller = deal_room.listing, deal_room.buyer, deal_room.seller
    lm = deal_room.offers.order_by("-created_at").values_list("message", flat=True).first()
    msg = lm or ""
    lead = Lead.all_objects.filter(listing=listing, buyer=buyer, is_deleted=False).first()
    if lead is None:
        lead = Lead.all_objects.filter(listing=listing, buyer=buyer).order_by("-pk").first()
        if lead is not None and lead.is_deleted:
            lead.restore()
            lead.seller = seller; lead.buyer_name = buyer.name
            lead.message = msg; lead.deal_room = deal_room
            lead.save(update_fields=["seller","buyer_name","message","deal_room","updated_at"])
            return lead
        return Lead.objects.create(listing=listing, buyer=buyer, seller=seller,
            buyer_name=buyer.name, message=msg, source=Lead.Source.DEAL,
            status=Lead.Status.NEW, deal_room=deal_room, message_count=1)
    Lead.objects.filter(pk=lead.pk).update(message_count=models.F("message_count")+1,
                                           updated_at=timezone.now())
    lead.refresh_from_db(); return lead
