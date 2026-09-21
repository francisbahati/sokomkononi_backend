from django.conf import settings
from django.db import models


class ContactMessage(models.Model):
    class Status(models.TextChoices):
        NEW = "NEW", "New"
        READ = "READ", "Read"
        REPLIED = "REPLIED", "Replied"
        ARCHIVED = "ARCHIVED", "Archived"

    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=255)
    message = models.TextField()

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW,
    )
    replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="contact_replies",
    )
    reply_note = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "contact_messages"
        ordering = ["-created_at"]
        verbose_name = "Ujumbe wa mawasiliano"
        verbose_name_plural = "Ujumbe wa mawasiliano"

    def __str__(self):
        return f"{self.name} — {self.subject}"
