import logging

from django.conf import settings
from rest_framework import serializers

from .models import VerificationDocument, VerificationRequest

logger = logging.getLogger(__name__)


class VerificationDocumentSerializer(serializers.ModelSerializer):
    """
    Serializer kwa verification document.

    Inarudisha URL mbili:
      • `url`         — signed URL (expires baada ya SIGNED_URL_EXPIRY sec)
      • `preview_url` — signed URL kwa preview (pia expires)

    Kama storage haisupport signed URLs (mfano FileSystemStorage),
    inarudisha URL ya kawaida kama fallback.
    """
    url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    is_image = serializers.SerializerMethodField()
    is_pdf = serializers.SerializerMethodField()

    class Meta:
        model = VerificationDocument
        fields = [
            "id", "name", "url", "preview_url",
            "is_image", "is_pdf", "uploaded_at",
        ]
        read_only_fields = fields

    def _sign(self, obj):
        """
        Rudisha signed URL kama storage inasupport.
        La sivyo, rudisha URL ya kawaida.
        """
        if not obj.file:
            return None

        request = self.context.get("request")
        expiry = getattr(settings, "SIGNED_URL_EXPIRY", 3600)

        try:
            # PrivateR2Storage / S3Boto3Storage inasupport .url(name, expire=...)
            url = obj.file.storage.url(
                obj.file.name,
                expire=expiry,
            )
        except TypeError:
            # FileSystemStorage hairuhusu `expire`
            try:
                url = obj.file.url
            except Exception:
                return None
        except Exception:
            logger.exception(
                "[verifications] failed to sign URL for doc %s", obj.pk,
            )
            try:
                url = obj.file.url
            except Exception:
                return None

        if request and url and url.startswith("/"):
            return request.build_absolute_uri(url)
        return url

    def get_url(self, obj):
        return self._sign(obj)

    def get_preview_url(self, obj):
        return self._sign(obj)

    def get_is_image(self, obj):
        if not obj.file:
            return False
        name = (obj.name or obj.file.name or "").lower()
        return name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))

    def get_is_pdf(self, obj):
        if not obj.file:
            return False
        name = (obj.name or obj.file.name or "").lower()
        return name.endswith(".pdf")


class VerificationRequestSerializer(serializers.ModelSerializer):
    documents = VerificationDocumentSerializer(many=True, read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    is_both_roles = serializers.SerializerMethodField()
    current_role = serializers.SerializerMethodField()

    class Meta:
        model = VerificationRequest
        fields = [
            "id",
            "type",
            "status",
            "user",
            "user_name",
            "user_email",
            "subject",
            "subject_id",
            "notes",
            "documents",
            "documents_requested_at",
            "documents_request_message",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "rejection_reason",
            "is_both_roles",
            "current_role",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "user",
            "user_name",
            "user_email",
            "documents",
            "documents_requested_at",
            "documents_request_message",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "rejection_reason",
            "is_both_roles",
            "current_role",
            "created_at",
            "updated_at",
        ]

    def get_reviewed_by_name(self, obj):
        u = obj.reviewed_by
        if not u:
            return None
        return getattr(u, "name", None) or u.email or None

    def get_is_both_roles(self, obj):
        """
        Chaguo B: mfumo unadetect kama mtumiaji ni Both (Seller + Buyer).
        Inaangalia listings na deals za mtumiaji.
        """
        user = obj.user
        if not user:
            return False
        try:
            from apps.listings.models import Listing
            from apps.deals.models import DealRoom

            has_listings = Listing.objects.filter(
                seller=user, is_deleted=False,
            ).exists()
            has_deals = DealRoom.objects.filter(buyer=user).exists()
            return bool(has_listings and has_deals)
        except Exception:
            return False

    def get_current_role(self, obj):
        """
        Rudisha role ya mtumiaji kwa sasa: 'seller', 'buyer', 'both', 'neither'.
        Inahesabiwa kutoka listings + deals.
        """
        user = obj.user
        if not user:
            return "neither"
        try:
            from apps.listings.models import Listing
            from apps.deals.models import DealRoom

            has_listings = Listing.objects.filter(
                seller=user, is_deleted=False,
            ).exists()
            has_deals = DealRoom.objects.filter(buyer=user).exists()

            if has_listings and has_deals:
                return "both"
            if has_listings:
                return "seller"
            if has_deals:
                return "buyer"
            return "neither"
        except Exception:
            return "neither"


class VerificationCreateSerializer(serializers.Serializer):
    """
    Chaguo B: mtumiaji anachagua SELLER au BUYER pekee.
    Mfumo unadetect Both automatically.
    """
    type = serializers.ChoiceField(
        choices=[("SELLER", "Seller"), ("BUYER", "Buyer")],
    )
    subject = serializers.CharField(max_length=255)
    subject_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_subject(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Kichwa linahitajika.")
        return value


class VerificationRejectSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(
        required=True, allow_blank=False, trim_whitespace=True,
    )

    def validate_rejection_reason(self, value):
        value = (value or "").strip()
        if len(value) < 5:
            raise serializers.ValidationError(
                "Sababu ya kukataa lazima iwe na angalau herufi 5."
            )
        return value