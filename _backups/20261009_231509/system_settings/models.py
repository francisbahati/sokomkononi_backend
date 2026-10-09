from django.db import models


class Webhook(models.Model):
    event = models.CharField(max_length=100)
    url = models.URLField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webhooks"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event} → {self.url}"


class AppStoreLinks(models.Model):
    """
    Singleton (only one row). Enforced via `pk=1` convention.
    """
    play = models.URLField(blank=True)
    appstore = models.URLField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_store_links"

    def __str__(self):
        return "App Store Links"


class PlatformPolicy(models.Model):
    """
    Singleton (only one row). Enforced via `pk=1` convention.
    """
    listing_lifetime_days = models.PositiveIntegerField(default=60)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "platform_policy"
        verbose_name_plural = "Platform policy"

    def __str__(self):
        return "Platform Policy"