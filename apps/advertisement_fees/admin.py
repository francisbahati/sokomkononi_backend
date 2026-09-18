from django.contrib import admin

from .models import AdvertisementFeeConfig


@admin.register(AdvertisementFeeConfig)
class AdvertisementFeeConfigAdmin(admin.ModelAdmin):
    list_display = ("price", "days", "updated_at")

    def has_add_permission(self, request):
        return not AdvertisementFeeConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
