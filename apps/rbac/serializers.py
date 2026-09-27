from rest_framework import serializers

from .models import Role, StaffAssignment


class BilingualMixin:
    BILINGUAL_FIELDS = {}

    def to_internal_value(self, data):
        data = dict(data)
        for src, prefix in self.BILINGUAL_FIELDS.items():
            val = data.pop(src, None)
            if isinstance(val, dict):
                if "sw" in val:
                    data[f"{prefix}_sw"] = val["sw"]
                if "en" in val:
                    data[f"{prefix}_en"] = val["en"]
        return super().to_internal_value(data)


class RoleSerializer(BilingualMixin, serializers.ModelSerializer):
    BILINGUAL_FIELDS = {"label": "label", "description": "description"}

    label = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    label_sw = serializers.CharField(required=False, allow_blank=True, write_only=True)
    label_en = serializers.CharField(required=False, allow_blank=True, write_only=True)
    description_sw = serializers.CharField(required=False, allow_blank=True, write_only=True)
    description_en = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Role
        fields = [
            "id", "key", "label", "description",
            "label_sw", "label_en", "description_sw", "description_en",
            "permissions", "is_system", "created_at",
        ]
        read_only_fields = ["id", "is_system", "created_at"]

    def get_label(self, obj):
        return {"sw": obj.label_sw, "en": obj.label_en}

    def get_description(self, obj):
        return {"sw": obj.description_sw, "en": obj.description_en}


class StaffAssignmentSerializer(serializers.ModelSerializer):
    role_key = serializers.CharField(source="role.key", read_only=True)
    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = StaffAssignment
        fields = [
            "id", "user", "name", "email",
            "role", "role_key", "active", "added_at",
        ]
        read_only_fields = ["id", "name", "email", "role_key", "added_at"]


class StaffCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role_key = serializers.CharField(max_length=60)
    active = serializers.BooleanField(required=False, default=True)
