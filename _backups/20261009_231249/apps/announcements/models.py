from django.conf import settings
from django.db import models


class Announcement(models.Model):
    class Type(models.TextChoices):
        FEE_CHANGE = "FEE_CHANGE", "Fee Change"
        NEW_CATEGORY = "NEW_CATEGORY", "New Category"
        MAINTENANCE = "MAINTENANCE", "System Maintenance"
        PROMOTION = "PROMOTION", "Campaign/Promotion"

    type = models.CharField(
        max_length=30,
        choices=Type.choices,
        default=Type.MAINTENANCE,
    )
    title = models.CharField(max_length=255)
    title_en = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    message_en = models.TextField(blank=True)

    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_announcements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "announcements"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["sent", "created_at"],
                name="ann_sent_created_idx",
            ),
        ]

    def __str__(self):
        return self.title