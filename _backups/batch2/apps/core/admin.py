from django.contrib import admin
from django.contrib import messages


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
    Respects AUDIT_PROTECTED_MODEL_NAMES.
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
        count = 0
        for obj in queryset.filter(is_deleted=True):
            obj.restore()
            count += 1
        self.message_user(request, f"Vitu {count} vimerejeshwa.")

    @admin.action(description="Futa kabisa (mara moja)")
    def hard_delete_selected(self, request, queryset):
        from apps.core.constants import AUDIT_PROTECTED_MODEL_NAMES

        model = queryset.model
        key = (model._meta.app_label, model.__name__)
        if key in AUDIT_PROTECTED_MODEL_NAMES:
            self.message_user(
                request,
                f"{model._meta.verbose_name} inalindwa dhidi ya kufutwa "
                f"kabisa. Tumia trash API au contact superuser.",
                level=messages.ERROR,
            )
            return

        count = 0
        for obj in queryset:
            obj.hard_delete()
            count += 1
        self.message_user(request, f"Vitu {count} vimefutwa kabisa.")
