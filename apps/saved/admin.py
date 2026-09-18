from django.contrib import admin

from .models import SavedListing


@admin.register(SavedListing)
class SavedListingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "listing", "snapshot_price", "saved_at")
    list_filter = ("saved_at",)
    search_fields = ("user__name", "user__email", "listing__title")
    ordering = ("-saved_at",)
    readonly_fields = ("saved_at",)