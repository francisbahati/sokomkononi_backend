from django.contrib import admin

from .models import LeadingFeeConfig


@admin.register(LeadingFeeConfig)
class LeadingFeeConfigAdmin(admin.ModelAdmin):
    list_display = ("price", "days", "updated_at")

    def has_add_permission(self, request):
        return not LeadingFeeConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
