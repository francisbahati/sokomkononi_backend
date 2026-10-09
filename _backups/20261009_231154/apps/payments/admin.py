from django.contrib import admin

from .models import Payout


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = (
        "id", "created_by", "amount", "net_amount",
        "method", "account_number", "status",
        "fimi_status", "created_at",
    )
    list_filter = ("status", "method", "created_at")
    search_fields = (
        "withdrawal_id", "account_number", "account_name",
        "created_by__email", "created_by__name",
    )
    readonly_fields = (
        "withdrawal_id", "fee", "net_amount", "fimi_status",
        "raw_response", "last_synced_at",
        "created_at", "updated_at",
    )
    ordering = ("-created_at",)
