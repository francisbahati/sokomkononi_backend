from django.contrib import admin

from .models import Role, StaffAssignment


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("key", "label_sw", "label_en", "is_system", "created_at")
    list_filter = ("is_system",)
    search_fields = ("key", "label_sw", "label_en")
    ordering = ("key",)


@admin.register(StaffAssignment)
class StaffAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "active", "added_at")
    list_filter = ("active", "role")
    search_fields = ("user__email", "user__name")
    ordering = ("-added_at",)