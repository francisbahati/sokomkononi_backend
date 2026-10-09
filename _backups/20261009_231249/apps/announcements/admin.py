from django.contrib import admin

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "id", "type", "title", "sent", "scheduled_for", "created_at",
    )
    list_filter = ("type", "sent", "created_at")
    search_fields = ("title", "title_en", "message", "message_en")
    ordering = ("-created_at",)