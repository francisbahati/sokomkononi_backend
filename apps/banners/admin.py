from django.contrib import admin

from .models import BannerAd


@admin.register(BannerAd)
class BannerAdAdmin(admin.ModelAdmin):
    list_display = (
        "id", "listing_title", "seller_name",
        "amount", "active", "created_at", "expires_at",
    )
    list_filter = ("active", "created_at")
    search_fields = ("listing_title", "seller__email", "seller__name")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
