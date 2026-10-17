from django.contrib import admin

from .models import Payout, Refund


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


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = (
        "id", "promotion_type", "promotion_id",
        "user", "amount_paid", "amount_refunded",
        "status", "method", "created_at",
    )
    list_filter = ("status", "method", "promotion_type")
    search_fields = (
        "user__name", "user__email",
        "payment_reference", "refund_reference",
    )
    readonly_fields = ("created_at", "processed_at", "completed_at")
    ordering = ("-created_at",)