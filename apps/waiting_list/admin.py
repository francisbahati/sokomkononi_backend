from django.contrib import admin

from .models import WaitingListEntry


@admin.register(WaitingListEntry)
class WaitingListEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "listing",
        "buyer",
        "status",
        "position",
        "joined_at",
        "notified_at",
    )

    list_filter = (
        "status",
        "joined_at",
        "notified_at",
    )

    search_fields = (
        "listing__title",
        "buyer__name",
        "buyer__email",
    )

    ordering = (
        "listing",
        "position",
        "joined_at",
    )

    readonly_fields = (
        "joined_at",
        "updated_at",
    )