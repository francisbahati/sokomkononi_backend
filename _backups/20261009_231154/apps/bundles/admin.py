from django.contrib import admin

from .models import Bundle, BundlePurchase


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = (
        "code", "type", "name_sw", "price",
        "validity_days", "active", "featured", "ordering",
    )
    list_filter = ("type", "active", "featured")
    search_fields = ("code", "name_sw", "name_en")
    ordering = ("ordering", "price")
    list_editable = ("active", "featured", "ordering")


@admin.register(BundlePurchase)
class BundlePurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "bundle", "amount",
        "status", "paid_at", "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("user__email", "user__name", "bundle__code", "payment_reference")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
