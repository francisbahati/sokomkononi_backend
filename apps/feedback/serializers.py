from rest_framework import serializers

from .models import Feedback


class FeedbackSerializer(serializers.ModelSerializer):
    """
    Output shape matches the frontend `norm()` in feedbackStore.js.

    Both snake_case (canonical) and camelCase aliases are emitted so
    either consumer style works without code changes.
    """
    listingId = serializers.IntegerField(source="listing_id", read_only=True)
    userName = serializers.CharField(source="user_name", read_only=True)
    userEmail = serializers.CharField(source="user_email", read_only=True)
    adminReply = serializers.CharField(source="admin_reply", read_only=True)
    repliedAt = serializers.DateTimeField(source="replied_at", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    authorSide = serializers.CharField(source="author_side", read_only=True)

    class Meta:
        model = Feedback
        fields = [
            "id", "type", "subject", "message", "rating",
            "listing", "listingId",
            "user_name", "userName",
            "user_email", "userEmail",
            "author_side", "authorSide",
            "status",
            "admin_reply", "adminReply",
            "replied_at", "repliedAt",
            "created_at", "createdAt",
            "updated_at",
        ]
        read_only_fields = [
            "id", "user_name", "user_email", "status",
            "admin_reply", "replied_at", "created_at", "updated_at",
            "listingId", "userName", "userEmail",
            "adminReply", "repliedAt", "createdAt", "authorSide",
        ]


class FeedbackCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=Feedback.Type.choices,
        default=Feedback.Type.FEEDBACK,
    )
    subject = serializers.CharField(max_length=255)
    message = serializers.CharField()
    rating = serializers.IntegerField(
        required=False, allow_null=True, min_value=1, max_value=5,
    )
    listing_id = serializers.IntegerField(required=False, allow_null=True)
    author_side = serializers.ChoiceField(
        choices=Feedback.AuthorSide.choices,
        default=Feedback.AuthorSide.SELLER,
    )

    def validate_subject(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Kichwa kinahitajika.")
        return value

    def validate_message(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Ujumbe unahitajika.")
        return value

    def validate_listing_id(self, value):
        if value is None:
            return None
        from apps.listings.models import Listing
        if not Listing.all_objects.filter(pk=value).exists():
            raise serializers.ValidationError("Tangazo halipatikani.")
        return value


class FeedbackRespondSerializer(serializers.Serializer):
    admin_reply = serializers.CharField()

    def validate_admin_reply(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Jibu linahitajika.")
        return value
