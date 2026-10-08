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
    list_display = ("id", "title", "type", "active", "start_date", "end_date")
    list_filter = ("type", "active")
    search_fields = ("title",)