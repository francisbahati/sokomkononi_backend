# apps/notifications/management/commands/fix_old_deal_notifications.py
# (unda folda management/commands/ zenye __init__.py kama hazipo)
#
# Husahihisha notifications za zamani za deals: zilikuwa na action_url
# "/transactions/<id>" na id ya Transaction/Reservation/InspectionPeriod.
# Run:  python manage.py fix_old_deal_notifications [--dry-run]
from django.core.management.base import BaseCommand

from apps.notifications.models import Notification
from apps.transactions.models import (
    InspectionPeriod, Reservation, Transaction,
)


class Command(BaseCommand):
    help = "Fix old deal notifications (deal room id + frontend URL + side)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        qs = Notification.all_objects.filter(
            action_url__startswith="/transactions/",
        )
        fixed = skipped = 0
        for n in qs.iterator():
            txn = None
            try:
                if n.related_object_type == "Transaction":
                    txn = Transaction.objects.get(pk=n.related_object_id)
                elif n.related_object_type == "Reservation":
                    txn = Reservation.objects.select_related(
                        "transaction").get(pk=n.related_object_id).transaction
                elif n.related_object_type == "InspectionPeriod":
                    txn = InspectionPeriod.objects.select_related(
                        "transaction").get(pk=n.related_object_id).transaction
            except Exception:
                txn = None
            if txn is None:
                skipped += 1
                continue
            is_buyer = n.recipient_id == txn.buyer_id
            prefix = "/dashboard/buyer" if is_buyer else "/dashboard"
            n.related_object_type = "deal"
            n.related_object_id = txn.deal_room_id
            n.action_url = f"{prefix}/deals?deal={txn.deal_room_id}"
            n.side = "buyer" if is_buyer else "seller"
            if not opts["dry_run"]:
                n.save(update_fields=[
                    "related_object_type", "related_object_id",
                    "action_url", "side",
                ])
            fixed += 1
        # Notifications za deals app: action_url "/deals/<deal_room_id>"
        from apps.deals.models import DealRoom
        for n in Notification.all_objects.filter(
            action_url__startswith="/deals/",
        ).iterator():
            room = DealRoom.objects.filter(pk=n.related_object_id).first()
            if room is None:
                skipped += 1
                continue
            is_buyer = n.recipient_id == room.buyer_id
            prefix = "/dashboard/buyer" if is_buyer else "/dashboard"
            n.action_url = f"{prefix}/deals?deal={room.id}"
            n.side = "buyer" if is_buyer else "seller"
            if not opts["dry_run"]:
                n.save(update_fields=["action_url", "side"])
            fixed += 1

        self.stdout.write(f"fixed={fixed} skipped={skipped}"
                          + (" (dry-run)" if opts["dry_run"] else ""))