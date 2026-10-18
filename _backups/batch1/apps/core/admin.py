from django.contrib import admin
from django.utils.html import format_html


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
    """

    actions = ["restore_selected", "hard_delete_selected"]

    def get_queryset(self, request):
        # Use all_objects so deleted rows are reachable from admin.
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
        for obj in queryset.filter(is_deleted=True):
            obj.restore()
        self.message_user(request, "Vitu vilivyochaguliwa vimerejeshwa.")

    @admin.action(description="Futa kabisa (mara moja)")
    def hard_delete_selected(self, request, queryset):
        for obj in queryset:
            obj.hard_delete()
        self.message_user(request, "Vitu vilivyochaguliwa vimefutwa kabisa.")