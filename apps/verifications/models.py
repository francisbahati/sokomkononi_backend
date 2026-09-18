from django.conf import settings
from django.db import models


class VerificationRequest(models.Model):
    """
    One verification request. Covers sellers, buyers, properties,
    vehicles and businesses. Admin reviews and approves/rejects.
    """

    class Type(models.TextChoices):
        SELLER = "SELLER", "Seller"
        BUYER = "BUYER", "Buyer"
        PROPERTY = "PROPERTY", "Property"
        VEHICLE = "VEHICLE", "Vehicle"
        BUSINESS = "BUSINESS", "Business"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        verbose_name="Aina ya uthibitisho",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Hali",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_requests",
        verbose_name="Mtumiaji",
    )
    user_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Jina la mtumiaji",
    )
    user_email = models.EmailField(
        blank=True,
        verbose_name="Barua pepe ya mtumiaji",
    )

    subject = models.CharField(
        max_length=255,
        verbose_name="Kichwa",
    )
    subject_id = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name="ID ya kitu",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Maelezo",
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_verifications",
        verbose_name="Ilirekebishwa na",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Ilirekebishwa",
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name="Sababu ya kukataa",
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
        db_table = "verification_requests"
        ordering = ["-created_at"]
        verbose_name = "Ombi la uthibitisho"
        verbose_name_plural = "Maombi ya uthibitisho"

        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="vreq_status_created_idx",
            ),
            models.Index(
                fields=["type", "status"],
                name="vreq_type_status_idx",
            ),
            models.Index(
                fields=["user"],
                name="vreq_user_idx",
            ),
        ]

    def __str__(self):
        return f"{self.type} — {self.subject} ({self.status})"


class VerificationDocument(models.Model):
    """
    A file attached to a verification request.
    """

    request = models.ForeignKey(
        VerificationRequest,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="Ombi",
    )
    file = models.FileField(
        upload_to="verifications/",
        verbose_name="Faili",
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Jina la faili",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "verification_documents"
        ordering = ["uploaded_at"]
        verbose_name = "Nyaraka ya uthibitisho"
        verbose_name_plural = "Nyaraka za uthibitisho"

    def __str__(self):
        return self.name or f"Doc #{self.pk}"