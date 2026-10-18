"""
Data migration:
    Listing.status  AVAILABLE -> LIVE
    DealRoom.status AGREED    -> ACCEPTED
    DealRoom.status CLOSED    -> COMPLETED
"""
from django.db import migrations


def forwards(apps, schema_editor):
    Listing = apps.get_model("listings", "Listing")
    DealRoom = apps.get_model("deals", "DealRoom")

    Listing.objects.filter(status="AVAILABLE").update(status="LIVE")
    DealRoom.objects.filter(status="AGREED").update(status="ACCEPTED")
    DealRoom.objects.filter(status="CLOSED").update(status="COMPLETED")


def backwards(apps, schema_editor):
    Listing = apps.get_model("listings", "Listing")
    DealRoom = apps.get_model("deals", "DealRoom")

    Listing.objects.filter(status="LIVE").update(status="AVAILABLE")
    DealRoom.objects.filter(status="ACCEPTED").update(status="AGREED")
    DealRoom.objects.filter(status="COMPLETED").update(status="CLOSED")


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0018_alter_listing_status"),
        ("deals", "0002_remove_dealroom_unique_deal_room_listing_buyer_and_more"),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]
