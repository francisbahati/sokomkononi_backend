from django.conf import settings
from django.db import models

from apps.listings.models import Listing


class Conversation(models.Model):
    """
    A one-to-one chat thread between a buyer and a seller about a
    specific listing. Separate from DealRoom (which is the negotiation
    surface with formal offers); a Conversation is the general chat.
    """

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="conversations",
        verbose_name="Tangazo",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="buyer_conversations",
        verbose_name="Mnunuzi",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_conversations",
        verbose_name="Muuzaji",
    )

    last_message = models.TextField(
        blank=True,
        verbose_name="Ujumbe wa mwisho",
    )
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Muda wa ujumbe wa mwisho",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Imeundwa",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Imesasishwa",
    )

    class Meta:
        db_table = "conversations"
        ordering = ["-updated_at"]
        verbose_name = "Mazungumzo"
        verbose_name_plural = "Mazungumzo"

        constraints = [
            models.UniqueConstraint(
                fields=["listing", "buyer", "seller"],
                name="unique_conversation_triple",
            ),
        ]
        indexes = [
            models.Index(
                fields=["buyer", "updated_at"],
                name="conv_buyer_updated_idx",
            ),
            models.Index(
                fields=["seller", "updated_at"],
                name="conv_seller_updated_idx",
            ),
        ]

    def __str__(self):
        return f"Conv #{self.pk} — {self.listing.title}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    text = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["conversation", "created_at"],
                name="msg_conv_created_idx",
            ),
            models.Index(
                fields=["conversation", "is_read"],
                name="msg_conv_read_idx",
            ),
        ]

    def __str__(self):
        return f"Msg #{self.pk} — conv {self.conversation_id}"