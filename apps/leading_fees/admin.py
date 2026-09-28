from django.contrib import admin

from .models import LeadingFeeConfig, ListingLeading


@admin.register(LeadingFeeConfig)
class LeadingFeeConfigAdmin(admin.ModelAdmin):
    list_display = ("price", "days", "updated_at")

    def has_add_permission(self, request):
        return not LeadingFeeConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ListingLeading)
class ListingLeadingAdmin(admin.ModelAdmin):
    list_display = (
        "id", "listing", "seller", "days", "price",
        "payment_status", "status", "starts_at", "expires_at", "created_at",
    )
    list_filter = ("payment_status", "status")
    search_fields = ("listing__title", "seller__name", "seller__email", "payment_reference")
    ordering = ("-created_at",)
