# apps/push/models.py
from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """
    Subscription ya Service Worker kwa push notifications.

    Kila kifaa/browser kina subscription yake. Mtumiaji anaweza kuwa
    na subscriptions nyingi (simu + laptop). Tuma kwa zote.

    `endpoint` ni URL ya kipekee ya push service (Firefox, Chrome, Safari).
    `p256dh` na `auth` ni keys za encryption.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
        verbose_name="Mtumiaji",
    )
    endpoint = models.URLField(
        max_length=500,
        unique=True,
        verbose_name="Endpoint",
    )
    p256dh = models.CharField(
        max_length=200,
        verbose_name="P256DH key",
    )
    auth = models.CharField(
        max_length=100,
        verbose_name="Auth key",
    )
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="User Agent",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Ilitumika mwisho",
    )

    class Meta:
        db_table = "push_subscriptions"
        ordering = ["-created_at"]
        verbose_name = "Push subscription"
        verbose_name_plural = "Push subscriptions"

        indexes = [
            models.Index(
                fields=["user"],
                name="push_sub_user_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.endpoint[:50]}…"