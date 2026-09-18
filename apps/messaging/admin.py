from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("sender", "text", "is_read", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "listing", "buyer", "seller",
        "last_message_at", "updated_at",
    )
    list_filter = ("created_at", "updated_at")
    search_fields = (
        "listing__title", "buyer__name", "buyer__email",
        "seller__name", "seller__email",
    )
    readonly_fields = ("created_at", "updated_at", "last_message_at")
    inlines = [MessageInline]
    ordering = ("-updated_at",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("conversation__listing__title", "sender__email", "text")
    ordering = ("-created_at",)