from django.contrib import admin

from .models import VerificationDocument, VerificationRequest


class VerificationDocumentInline(admin.TabularInline):
    model = VerificationDocument
    extra = 0
    readonly_fields = ("uploaded_at",)


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id", "type", "subject", "user_name",
        "status", "reviewed_at", "created_at",
    )
    list_filter = ("type", "status", "created_at")
    search_fields = ("subject", "user_name", "user_email", "notes")
    readonly_fields = ("created_at", "updated_at", "reviewed_at")
    inlines = [VerificationDocumentInline]
    ordering = ("-created_at",)