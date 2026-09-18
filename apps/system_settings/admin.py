from django.contrib import admin

from .models import AppStoreLinks, PlatformPolicy, Webhook


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "url", "active", "created_at")
    list_filter = ("event", "active")
    search_fields = ("url",)
    ordering = ("-created_at",)


@admin.register(AppStoreLinks)
class AppStoreLinksAdmin(admin.ModelAdmin):
    list_display = ("play", "appstore", "updated_at")


@admin.register(PlatformPolicy)
class PlatformPolicyAdmin(admin.ModelAdmin):
    list_display = ("listing_lifetime_days", "updated_at")