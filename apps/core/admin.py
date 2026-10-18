# apps/core/admin.py
from django.contrib import admin, messages
from django.db.models import ProtectedError


class DeletedFilter(admin.SimpleListFilter):
    title = "Imefutwa"
    parameter_name = "deleted"

    def lookups(self, request, model_admin):
        return [
            ("no", "Hai"),
            ("yes", "Kwenye kikapu"),
            ("all", "Zote"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(is_deleted=True)
        if self.value() == "no":
            return queryset.filter(is_deleted=False)
        return queryset


class SoftDeleteAdminMixin:
    """
    Show soft-deleted rows in admin, allow restore / hard-delete.

    Admin anaweza kufuta kila kitu. Models zilizo kwenye
    AUDIT_PROTECTED_MODEL_NAMES zinaonyeshwa onyo (warning) lakini
    bado zinafutwa — superuser pekee anapaswa kufanya hivi.
    """

    actions = ["restore_selected", "hard_delete_selected"]

    def get_queryset(self, request):
        return self.model.all_objects.all()

    def get_list_filter(self, request):
        base = list(super().get_list_filter(request))
        if DeletedFilter not in base:
            base.append(DeletedFilter)
        return base

    def get_list_display(self, request):
        base = list(super().get_list_display(request))
        if "is_deleted" not in base:
            base.append("is_deleted")
        return base

    @admin.action(description="Rejesha vilivyochaguliwa")
    def restore_selected(self, request, queryset):
        n = 0
        for obj in queryset.filter(is_deleted=True):
            obj.restore()
            n += 1
        self.message_user(request, f"Vitu {n} vimerejeshwa.")

    @admin.action(description="Futa kabisa (mara moja)")
    def hard_delete_selected(self, request, queryset):
        from apps.core.constants import AUDIT_PROTECTED_MODEL_NAMES

        model = queryset.model
        key = (model._meta.app_label, model.__name__)
        is_protected_model = key in AUDIT_PROTECTED_MODEL_NAMES

        deleted = 0
        protected = []
        for obj in queryset:
            try:
                obj.hard_delete()
                deleted += 1
            except ProtectedError as e:
                protected.append(
                    f"{obj._meta.label}#{obj.pk} "
                    f"({len(e.protected_objects)} related)"
                )

        if deleted:
            prefix = (
                "⚠️ Model hii inalindwa, lakini umeifuta kwa tahadhari. "
                if is_protected_model
                else ""
            )
            self.message_user(
                request,
                f"{prefix}Vitu {deleted} vimefutwa kabisa.",
                level=messages.WARNING if is_protected_model else messages.SUCCESS,
            )

        if protected:
            self.message_user(
                request,
                "Vitu vifuatavyo havikufutwa kwa sababu vina "
                "mahusiano yanayolindwa (PROTECT): " + "; ".join(protected[:10]),
                level=messages.WARNING,
            )