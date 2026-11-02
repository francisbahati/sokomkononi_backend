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
    def save(self, *a, **k):
        self.pk = 1
        super().save(*a, **k)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

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
    def save(self, *a, **k):
        self.pk = 1
        super().save(*a, **k)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

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


class ContactInfo(models.Model):
    def save(self, *a, **k):
        self.pk = 1
        super().save(*a, **k)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    """
    Singleton (only one row). Enforced via `pk=1` convention.
    """
    email = models.EmailField(default="support@sokomkononi.co.tz")
    phone = models.CharField(max_length=20, default="+255743895038")
    whatsapp = models.CharField(max_length=20, default="255743895038")
    address = models.CharField(max_length=255, default="Dar es Salaam, Tanzania")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "contact_info"
        verbose_name = "Contact Info"
        verbose_name_plural = "Contact Info"

    def __str__(self):
        return self.email