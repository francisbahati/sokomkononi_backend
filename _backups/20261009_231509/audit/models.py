from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """
    A single admin action. Persisted for compliance and review.
    """

    action = models.CharField(
        max_length=100,
        verbose_name="Kitendo",
    )
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Msimamizi",
    )
    admin_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Jina la msimamizi",
    )
    target = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Kitu",
    )
    target_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="ID ya kitu",
    )
    details = models.TextField(
        blank=True,
        verbose_name="Maelezo",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Imeundwa",
    )

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        verbose_name = "Kumbukumbu ya kitendo"
        verbose_name_plural = "Kumbukumbu za matendo"

        indexes = [
            models.Index(
                fields=["admin_user", "created_at"],
                name="audit_admin_created_idx",
            ),
            models.Index(
                fields=["action", "created_at"],
                name="audit_action_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.action} — {self.admin_name} — {self.created_at:%Y-%m-%d %H:%M}"