from django.conf import settings
from django.db import models


class Feedback(models.Model):
    """
    Seller / Buyer feedback, problem report, suggestion, or rating.
    Surfaces in the user's own "My Feedback" page and in Admin →
    Customer Care → Feedback tab.
    """

    class Type(models.TextChoices):
        FEEDBACK = "feedback", "Maoni"
        PROBLEM = "problem", "Tatizo"
        SUGGESTION = "suggestion", "Pendekezo"
        RATING = "rating", "Kadiria Uzoefu"

    class Status(models.TextChoices):
        NEW = "new", "Mpya"
        ANSWERED = "answered", "Imejibiwa"
        ARCHIVED = "archived", "Kumbukumbu"

    class AuthorSide(models.TextChoices):
        SELLER = "seller", "Muuzaji"
        BUYER = "buyer", "Mnunuzi"
        BOTH = "both", "Wote"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="feedback_items",
    )
    user_name = models.CharField(max_length=150, blank=True)
    user_email = models.EmailField(blank=True)

    author_side = models.CharField(
        max_length=10,
        choices=AuthorSide.choices,
        default=AuthorSide.SELLER,
    )

    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.FEEDBACK,
    )

    subject = models.CharField(max_length=255)
    message = models.TextField()

    rating = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="1..5 when type=rating",
    )

    listing = models.ForeignKey(
        "listings.Listing",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="feedback_items",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
    )

    admin_reply = models.TextField(blank=True)
    replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="feedback_replies",
    )
    replied_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "feedback"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["type", "status"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"[{self.type}] {self.subject[:40]} — {self.user_email}"
