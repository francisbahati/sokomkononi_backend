from django.conf import settings
from django.db import models


class UserCredit(models.Model):
    """
    Credits held by a user for a particular service key
    ("listing", "boost", "leading", "reservation", "ads", "premium").
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="credits",
        verbose_name="Mtumiaji",
    )
    service_key = models.CharField(
        max_length=50,
        verbose_name="Huduma",
    )
    remaining = models.PositiveIntegerField(default=0, verbose_name="Zilizobaki")
    total = models.PositiveIntegerField(default=0, verbose_name="Jumla")

    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Inaisha",
    )

    last_bundle_code = models.CharField(max_length=100, blank=True)
    last_bundle_name = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_credits"
        ordering = ["service_key"]
        verbose_name = "Credit ya mtumiaji"
        verbose_name_plural = "Credits za watumiaji"

        constraints = [
            models.UniqueConstraint(
                fields=["user", "service_key"],
                name="uniq_user_credit_service",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "service_key"],
                name="uc_user_service_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.service_key}: {self.remaining}/{self.total}"


class UserService(models.Model):
    """
    Features granted to a user via bundle purchase:
    "priority_visibility", "premium_badge", "profile_enhancement", etc.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name="Mtumiaji",
    )
    service_key = models.CharField(max_length=50, verbose_name="Huduma")

    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Inaisha",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_services"
        ordering = ["service_key"]
        verbose_name = "Huduma ya mtumiaji"
        verbose_name_plural = "Huduma za watumiaji"

        constraints = [
            models.UniqueConstraint(
                fields=["user", "service_key"],
                name="uniq_user_service",
            ),
        ]

    def __str__(self):
        return f"{self.user} — {self.service_key}"
