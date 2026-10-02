# apps/reservation_rates/admin.py
from django.contrib import admin

from .models import ReservationRate


@admin.register(ReservationRate)
class ReservationRateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "flat_fee",
        "days",
        "is_enabled",
        "updated_at",
    )

    list_editable = (
        "flat_fee",
        "days",
        "is_enabled",
    )

    readonly_fields = (
        "id",
        "updated_at",
    )

    def has_add_permission(self, request):
        # Singleton — hakuna kuongeza zaidi ya moja
        return not ReservationRate.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Singleton — hairuhusiwi kufuta
        return False