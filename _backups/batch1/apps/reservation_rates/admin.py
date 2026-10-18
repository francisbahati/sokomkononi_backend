# apps/reservation_rates/admin.py
from django.contrib import admin

from .models import ReservationSettings, ReservationTier


@admin.register(ReservationSettings)
class ReservationSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "is_enabled", "updated_at")
    list_filter = ("is_enabled",)

    def has_add_permission(self, request):
        # Singleton — hakuna kuongeza zaidi ya mmoja
        return not ReservationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Usiruhusu kufuta singleton
        return False


@admin.register(ReservationTier)
class ReservationTierAdmin(admin.ModelAdmin):
    list_display = ("id", "hours", "fee", "is_active", "order", "updated_at")
    list_filter = ("is_active",)
    list_editable = ("fee", "is_active", "order")
    ordering = ("order", "hours")
    search_fields = ("hours",)