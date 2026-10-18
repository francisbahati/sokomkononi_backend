# apps/leading_fees/admin.py
from django.contrib import admin

from .models import LeadingFeeConfig, LeadingPackage, ListingLeading


@admin.register(LeadingFeeConfig)
class LeadingFeeConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "is_enabled", "label_sw", "updated_at")
    list_filter = ("is_enabled",)

    def has_add_permission(self, request):
        # Singleton — hakuna kuongeza zaidi ya mmoja
        return not LeadingFeeConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LeadingPackage)
class LeadingPackageAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "duration_hours", "price",
        "is_active", "ordering", "updated_at",
    )
    list_filter = ("is_active",)
    list_editable = ("price", "is_active", "ordering")
    ordering = ("ordering", "duration_hours")
    search_fields = ("name",)


@admin.register(ListingLeading)
class ListingLeadingAdmin(admin.ModelAdmin):
    list_display = (
        "id", "listing", "seller", "package",
        "days", "price", "payment_status", "status",
        "expires_at", "created_at",
    )
    list_filter = ("payment_status", "status")
    search_fields = ("listing__title", "seller__name")
    raw_id_fields = ("listing", "seller", "package")