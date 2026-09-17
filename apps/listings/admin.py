from django.contrib import admin

from apps.core.admin import SoftDeleteAdminMixin

from .models import Listing, ListingImage


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1
    fields = (
        "image",
        "is_primary",
        "ordering",
    )


@admin.register(Listing)
class ListingAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "title",
        "seller",
        "category",
        "price",
        "status",
        "is_featured",
        "is_boosted",
        "is_deleted",
        "views_count",
        "created_at",
    )

    list_filter = (
        "status",
        "category",
        "is_featured",
        "is_boosted",
    )

    search_fields = (
        "title",
        "description",
        "location",
        "seller__name",
        "seller__email",
        "seller__phone",
    )

    ordering = (
        "-created_at",
    )

    readonly_fields = (
        "views_count",
        "created_at",
        "updated_at",
        "deleted_at",
        "deleted_by",
    )

    list_editable = (
        "status",
        "is_featured",
        "is_boosted",
    )

    inlines = [
        ListingImageInline,
    ]


@admin.register(ListingImage)
class ListingImageAdmin(admin.ModelAdmin):
    list_display = (
        "listing",
        "is_primary",
        "ordering",
        "created_at",
    )

    list_filter = (
        "is_primary",
    )

    search_fields = (
        "listing__title",
    )

    ordering = (
        "listing",
        "ordering",
    )

    readonly_fields = (
        "created_at",
    )