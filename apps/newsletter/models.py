import uuid

from django.db import models


class NewsletterSubscriber(models.Model):
    """Mtu aliyejiunga na jarida (fomu ya NewsletterStrip)."""

    email = models.EmailField(unique=True, verbose_name="Barua pepe")
    is_active = models.BooleanField(default=True, verbose_name="Anapokea jarida")
    lang = models.CharField(max_length=5, blank=True, default="", verbose_name="Lugha")
    source = models.CharField(
        max_length=40, blank=True, default="homepage", verbose_name="Chanzo",
    )
    unsubscribe_token = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False,
    )
    subscribed_at = models.DateTimeField(auto_now_add=True, verbose_name="Alijiunga")
    unsubscribed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Alijiondoa",
    )

    class Meta:
        db_table = "newsletter_subscribers"
        ordering = ["-subscribed_at"]
        indexes = [
            models.Index(fields=["is_active", "subscribed_at"], name="newsletter_active_idx"),
        ]

    def __str__(self):
        return self.email
