# apps/banners/admin.py
from django.contrib import admin

from .models import BannerAd, Campaign


@admin.register(BannerAd)
class BannerAdAdmin(admin.ModelAdmin):
    list_display = (
        "id", "listing_title", "seller_name", "package",
        "amount", "payment_status", "active",
        "expires_at", "created_at",
    )
    list_filter = ("payment_status", "active")
    search_fields = ("listing_title", "seller_name")
    raw_id_fields = ("listing", "seller", "package")


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = (
        "id", "get_name", "discount_percent", "applies_to",
        "start_date", "end_date", "active", "created_at",
    )
    list_filter = ("applies_to", "active", "type")
    search_fields = ("name",)
    list_editable = ("active",)

    @admin.display(description="Name")
    def get_name(self, obj):
        if isinstance(obj.name, dict):
            return obj.name.get("sw") or obj.name.get("en") or f"#{obj.pk}"
        return str(obj.name or f"#{obj.pk}")