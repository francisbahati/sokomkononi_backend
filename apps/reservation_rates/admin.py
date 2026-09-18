from django.contrib import admin

from .models import ReservationRate


@admin.register(ReservationRate)
class ReservationRateAdmin(admin.ModelAdmin):
    list_display = ("tier", "hours", "label_sw", "fee", "ordering")
    list_editable = ("fee", "ordering")
    ordering = ("ordering",)
