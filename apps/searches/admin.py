from django.contrib import admin

from .models import SavedSearch, SavedSearchMatch


@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "name", "category_slug", "region",
        "match_count", "created_at",
    )
    list_filter = ("verified_only", "category_slug", "created_at")
    search_fields = ("user__name", "user__email", "name", "query", "region")
    ordering = ("-created_at",)


@admin.register(SavedSearchMatch)
class SavedSearchMatchAdmin(admin.ModelAdmin):
    list_display = ("id", "search", "listing", "notified_at")
    search_fields = ("search__name", "listing__title")
    ordering = ("-notified_at",)