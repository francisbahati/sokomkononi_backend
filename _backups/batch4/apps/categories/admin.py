from django.contrib import admin

from apps.core.admin import SoftDeleteAdminMixin

from .models import Category


@admin.register(Category)
class CategoryAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "is_active",
        "ordering",
        "is_deleted",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "slug",
        "description",
    )

    ordering = (
        "ordering",
        "name",
    )

    readonly_fields = (
        "slug",
        "created_at",
        "updated_at",
        "deleted_at",
        "deleted_by",
    )

    list_editable = (
        "is_active",
        "ordering",
    )