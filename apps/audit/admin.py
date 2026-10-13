from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id", "action", "admin_name", "target",
        "target_id", "created_at",
    )
    list_filter = ("action", "created_at")
    search_fields = ("admin_name", "target", "details")
    readonly_fields = ("created_at",)

    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    ordering = ("-created_at",)