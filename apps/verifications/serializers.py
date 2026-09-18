from rest_framework import serializers

from .models import VerificationDocument, VerificationRequest


class VerificationDocumentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = VerificationDocument
        fields = ["id", "name", "url", "uploaded_at"]
        read_only_fields = fields

    def get_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url


class VerificationRequestSerializer(serializers.ModelSerializer):
    documents = VerificationDocumentSerializer(many=True, read_only=True)

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
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
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
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]


class VerificationCreateSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=VerificationRequest.Type.choices)
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