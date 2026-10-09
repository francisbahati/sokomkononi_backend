from rest_framework import serializers

from .models import Role, StaffAssignment


class RoleSerializer(serializers.ModelSerializer):
    label = serializers.DictField(required=False, write_only=True)
    description = serializers.DictField(required=False, write_only=True)

    label_out = serializers.SerializerMethodField()
    description_out = serializers.SerializerMethodField()

    label_sw = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    label_en = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description_sw = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    description_en = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Role
        fields = [
            "id", "key",
            "label", "label_out",
            "description", "description_out",
            "label_sw", "label_en", "description_sw", "description_en",
            "permissions", "is_system", "created_at",
        ]
        read_only_fields = ["id", "is_system", "created_at"]

    def get_label_out(self, obj):
        return {"sw": obj.label_sw, "en": obj.label_en}

    def get_description_out(self, obj):
        return {"sw": obj.description_sw, "en": obj.description_en}

    def to_internal_value(self, data):
        data = dict(data)
        label = data.pop("label", None)
        if isinstance(label, dict):
            if "sw" in label:
                data.setdefault("label_sw", label["sw"])
            if "en" in label:
                data.setdefault("label_en", label["en"])
        desc = data.pop("description", None)
        if isinstance(desc, dict):
            if "sw" in desc:
                data.setdefault("description_sw", desc["sw"])
            if "en" in desc:
                data.setdefault("description_en", desc["en"])
        return super().to_internal_value(data)

    def create(self, validated_data):
        validated_data.pop("label", None)
        validated_data.pop("description", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("label", None)
        validated_data.pop("description", None)
        return super().update(instance, validated_data)


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
