from django.conf import settings
from django.db import models


class Ticket(models.Model):
    class Category(models.TextChoices):
        PAYMENT = "PAYMENT", "Payment"
        VERIFICATION = "VERIFICATION", "Verification"
        DISPUTE = "DISPUTE", "Dispute"
        LISTING = "LISTING", "Listing"
        ACCOUNT = "ACCOUNT", "Account"
        OTHER = "OTHER", "Other"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Namba ya ticket",
    )

    subject = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
        verbose_name="Mtumiaji",
    )
    user_name = models.CharField(max_length=150, blank=True)
    user_email = models.EmailField(blank=True)

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        verbose_name="Amepewa",
    )
    assigned_to_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Jina la aliyepewa",
    )

    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tickets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="ticket_status_created_idx",
            ),
            models.Index(
                fields=["user", "status"],
                name="ticket_user_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.code} — {self.subject}"


class TicketMessage(models.Model):
    class Sender(models.TextChoices):
        USER = "USER", "User"
        ADMIN = "ADMIN", "Admin"

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="messages",
    )
    sender = models.CharField(
        max_length=10, choices=Sender.choices, default=Sender.USER,
    )
    sender_name = models.CharField(max_length=150, blank=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ticket_messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["ticket", "created_at"],
                name="tmsg_ticket_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.ticket.code} — {self.sender}"