# apps/verifications/admin.py

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import VerificationDocument, VerificationRequest
from .notify import (
    notify_approved,
    notify_documents_requested,
    notify_rejected,
)


# ============================================================
# INLINE: VerificationDocument
# ============================================================
class VerificationDocumentInline(admin.TabularInline):
    model = VerificationDocument
    extra = 0
    fields = ("name", "file", "file_link", "uploaded_at")
    readonly_fields = ("file", "file_link", "uploaded_at")

    def file_link(self, obj):
        """Link ya kupakua file kwenye admin (kwa preview)."""
        if not obj or not obj.pk or not obj.file:
            return "—"
        try:
            url = obj.file.url
        except Exception:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Fungua</a>',
            url,
        )

    file_link.short_description = _("Faili")


# ============================================================
# ADMIN: VerificationRequest
# ============================================================
@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "type",
        "subject",
        "user_name",
        "status",
        "reviewed_at",
        "created_at",
    )
    list_filter = ("type", "status", "created_at")
    search_fields = ("subject", "user_name", "user_email", "notes")
    readonly_fields = (
        "created_at",
        "updated_at",
        "reviewed_at",
        "reviewed_by",
    )
    inlines = [VerificationDocumentInline]
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("user", "reviewed_by")
    list_per_page = 50
    autocomplete_fields = ("user",)

    # Maombi yanaundwa kupitia API (frontend), si admin.
    # Kuzuia admin kuunda kwa mkono kunazuia data inconsistency.
    def has_add_permission(self, request):
        return False

    fieldsets = (
        (_("Taarifa za ombi"), {
            "fields": (
                "type", "status", "subject", "subject_id", "notes",
            ),
        }),
        (_("Mtumiaji"), {
            "fields": (
                "user", "user_name", "user_email",
            ),
        }),
        (_("Ukaguzi"), {
            "fields": (
                "reviewed_by", "reviewed_at", "rejection_reason",
            ),
            "classes": ("collapse",),
        }),
        (_("Nyaraka zaidi"), {
            "fields": (
                "documents_requested_at", "documents_request_message",
            ),
            "classes": ("collapse",),
        }),
        (_("Muda"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    # ──────────────────────────────────────────────────────────
    # ACTIONS
    # ──────────────────────────────────────────────────────────
    actions = ("approve_selected", "reject_selected", "request_documents_selected")

    @admin.action(description=_("Idhinisha maombi yaliyochaguliwa"))
    def approve_selected(self, request, queryset):
        pending = queryset.filter(status=VerificationRequest.Status.PENDING)
        total = pending.count()
        if not total:
            self.message_user(
                request,
                _("Hakuna maombi ya PENDING kwenye uteuzi."),
                level=messages.WARNING,
            )
            return

        approved, failed = 0, 0
        for obj in pending:
            try:
                obj.status = VerificationRequest.Status.APPROVED
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()
                obj.save(update_fields=[
                    "status", "reviewed_by", "reviewed_at", "updated_at",
                ])

                # is_verified
                target_user = obj.user
                if target_user and obj.type in (
                    VerificationRequest.Type.SELLER,
                    VerificationRequest.Type.BUYER,
                ):
                    target_user.is_verified = True
                    target_user.save(
                        update_fields=["is_verified", "updated_at"],
                    )

                # notifications (on_commit itasubiri commit;
                # hapa hakuna atomic kwa sababu admin action ni bulk —
                # kila ombi lina jukumu lake)
                notify_approved(obj)
                approved += 1
            except Exception:
                failed += 1

        if approved:
            self.message_user(
                request,
                _("Maombi %(n)s yameidhinishwa.") % {"n": approved},
                level=messages.SUCCESS,
            )
        if failed:
            self.message_user(
                request,
                _("Maombi %(n)s yameshindwa.") % {"n": failed},
                level=messages.ERROR,
            )

    @admin.action(description=_("Kataa maombi yaliyochaguliwa"))
    def reject_selected(self, request, queryset):
        """
        Bulk reject inahitaji sababu. Admin anaingiza kupitia intermediate page.
        Kwa urahisi, tunatumia default reason — admin anaweza kuibadilisha
        baadaye kupitia API au admin detail page.
        """
        pending = queryset.filter(status=VerificationRequest.Status.PENDING)
        total = pending.count()
        if not total:
            self.message_user(
                request,
                _("Hakuna maombi ya PENDING kwenye uteuzi."),
                level=messages.WARNING,
            )
            return

        # Bulk reject haitoi fomu ya sababu (admin anaweza kutumia API
        # kwa sababu maalum). Tunatumia default.
        default_reason = _(
            "Ombi limekataliwa na admin. Tafadhali wasiliana na support "
            "kwa maelezo zaidi."
        )

        rejected, failed = 0, 0
        for obj in pending:
            try:
                obj.status = VerificationRequest.Status.REJECTED
                obj.rejection_reason = str(default_reason)
                obj.reviewed_by = request.user
                obj.reviewed_at = timezone.now()
                obj.save(update_fields=[
                    "status", "rejection_reason", "reviewed_by",
                    "reviewed_at", "updated_at",
                ])
                notify_rejected(obj, str(default_reason))
                rejected += 1
            except Exception:
                failed += 1

        if rejected:
            self.message_user(
                request,
                _("Maombi %(n)s yamekataliwa.") % {"n": rejected},
                level=messages.SUCCESS,
            )
        if failed:
            self.message_user(
                request,
                _("Maombi %(n)s yameshindwa.") % {"n": failed},
                level=messages.ERROR,
            )

    @admin.action(description=_("Omba nyaraka zaidi (kwa uteuzi)"))
    def request_documents_selected(self, request, queryset):
        pending = queryset.filter(status=VerificationRequest.Status.PENDING)
        total = pending.count()
        if not total:
            self.message_user(
                request,
                _("Hakuna maombi ya PENDING kwenye uteuzi."),
                level=messages.WARNING,
            )
            return

        default_message = _(
            "Tafadhali pakia nyaraka za ziada ili kukamilisha uthibitisho."
        )
        done, failed = 0, 0
        for obj in pending:
            try:
                obj.documents_requested_at = timezone.now()
                obj.documents_request_message = str(default_message)
                obj.save(update_fields=[
                    "documents_requested_at",
                    "documents_request_message",
                    "updated_at",
                ])
                notify_documents_requested(obj, str(default_message))
                done += 1
            except Exception:
                failed += 1

        if done:
            self.message_user(
                request,
                _("Maombi %(n)s yameombwa nyaraka.") % {"n": done},
                level=messages.SUCCESS,
            )
        if failed:
            self.message_user(
                request,
                _("Maombi %(n)s yameshindwa.") % {"n": failed},
                level=messages.ERROR,
            )