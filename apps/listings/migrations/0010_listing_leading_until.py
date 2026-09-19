# apps/listings/migrations/0010_listing_leading_until.py
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0009_listingfee_percentage_listingfee_rule_and_more"),
    ]
    operations = [
        migrations.AddField(
            model_name="listing",
            name="leading_until",
            field=models.DateTimeField(
                null=True, blank=True, db_index=True,
                verbose_name="Leading inaisha",
            ),
        ),
    ]
