# apps/advertisement_fees/admin.py
from django.contrib import admin

from .models import AdvertisementFeeConfig, AdvertisementPackage


@admin.register(AdvertisementFeeConfig)
class AdvertisementFeeConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "is_enabled", "label_sw", "updated_at")
    list_filter = ("is_enabled",)

    def has_add_permission(self, request):
        return not AdvertisementFeeConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AdvertisementPackage)
class AdvertisementPackageAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "duration_hours", "price",
        "is_active", "ordering", "updated_at",
    )
    list_filter = ("is_active",)
    list_editable = ("price", "is_active", "ordering")
    ordering = ("ordering", "duration_hours")
    search_fields = ("name",)