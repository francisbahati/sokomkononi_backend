from django.contrib import admin
from django.utils import timezone

from .models import NewsletterSubscriber


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "is_active", "lang", "source", "subscribed_at")
    list_filter = ("is_active", "lang", "source")
    search_fields = ("email",)
    readonly_fields = ("unsubscribe_token", "subscribed_at", "unsubscribed_at")
    actions = ["deactivate", "activate"]

    @admin.action(description="Zima (usitume jarida)")
    def deactivate(self, request, queryset):
        queryset.update(is_active=False, unsubscribed_at=timezone.now())

    @admin.action(description="Washa tena")
    def activate(self, request, queryset):
        queryset.update(is_active=True, unsubscribed_at=None)
