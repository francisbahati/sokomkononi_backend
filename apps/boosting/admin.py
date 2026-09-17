from django.contrib import admin

from apps.core.admin import SoftDeleteAdminMixin

from .models import BoostPackage, ListingBoost


@admin.register(BoostPackage)
class BoostPackageAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "duration_hours",
        "price",
        "is_active",
        "ordering",
        "is_deleted",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "description",
    )

    ordering = (
        "ordering",
        "duration_hours",
        "price",
    )

    list_editable = (
        "is_active",
        "ordering",
        "price",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "deleted_at",
        "deleted_by",
    )


@admin.register(ListingBoost)
class ListingBoostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "listing",
        "seller",
        "package",
        "amount",
        "payment_status",
        "status",
        "starts_at",
        "expires_at",
        "created_at",
    )

    list_filter = (
        "payment_status",
        "status",
        "package",
    )

    search_fields = (
        "listing__title",
        "seller__name",
        "seller__email",
        "payment_reference",
    )

    readonly_fields = (
        "amount",
        "paid_at",
        "starts_at",
        "expires_at",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )