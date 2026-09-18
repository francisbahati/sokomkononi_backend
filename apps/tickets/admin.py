from django.contrib import admin

from .models import Ticket, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "code", "subject", "user_name", "category",
        "priority", "status", "created_at",
    )
    list_filter = ("status", "priority", "category", "created_at")
    search_fields = ("code", "subject", "user_name", "user_email")
    readonly_fields = ("created_at", "updated_at", "resolved_at")
    inlines = [TicketMessageInline]
    ordering = ("-created_at",)


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ("ticket", "sender", "sender_name", "created_at")
    search_fields = ("ticket__code", "text")
    ordering = ("-created_at",)