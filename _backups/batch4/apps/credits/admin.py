from django.contrib import admin

from .models import UserCredit, UserService


@admin.register(UserCredit)
class UserCreditAdmin(admin.ModelAdmin):
    list_display = (
        "user", "service_key", "remaining", "total",
        "expires_at", "updated_at",
    )
    list_filter = ("service_key",)
    search_fields = ("user__email", "user__name")
    ordering = ("service_key",)


@admin.register(UserService)
class UserServiceAdmin(admin.ModelAdmin):
    list_display = ("user", "service_key", "expires_at", "granted_at")
    list_filter = ("service_key",)
    search_fields = ("user__email", "user__name")
    ordering = ("service_key",)
