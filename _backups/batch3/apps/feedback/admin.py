from django.contrib import admin

from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "id", "type", "subject", "user_name",
        "author_side", "status", "created_at",
    )
    list_filter = ("type", "status", "author_side", "created_at")
    search_fields = ("subject", "message", "user_name", "user_email")
    readonly_fields = ("created_at", "updated_at", "replied_at")
    ordering = ("-created_at",)
