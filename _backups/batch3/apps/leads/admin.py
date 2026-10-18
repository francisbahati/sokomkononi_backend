from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "id", "listing", "buyer_name", "seller", "status",
        "source", "message_count", "created_at",
    )
    list_filter = ("status", "source", "created_at")
    search_fields = (
        "listing__title", "buyer_name",
        "buyer__email", "seller__email",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)