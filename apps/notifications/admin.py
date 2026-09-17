from django.contrib import admin

from apps.core.admin import SoftDeleteAdminMixin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "recipient",
        "notification_type",
        "priority",
        "is_read",
        "is_deleted",
        "created_at",
    )

    list_filter = (
        "notification_type",
        "priority",
        "is_read",
        "created_at",
    )

    search_fields = (
        "recipient__name",
        "recipient__email",
        "title",
        "message",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "read_at",
        "deleted_at",
        "deleted_by",
    )

    ordering = (
        "-created_at",
    )