from django.contrib import admin

from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "is_active",
        "ordering",
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
    )

    list_editable = (
        "is_active",
        "ordering",
    )