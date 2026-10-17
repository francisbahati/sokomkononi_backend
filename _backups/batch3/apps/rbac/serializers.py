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


    VALID_PERMISSIONS = {
      "overview", "users", "moderation", "verification", "deals",
      "revenue", "bundles", "promotions", "reports", "support",
      "content", "audit", "trash", "system", "staff",
      "profile", 
      }

    def validate_permissions(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("permissions lazima iwe list.")
        bad = set(value) - self.VALID_PERMISSIONS
        if bad:
            raise serializers.ValidationError(
                f"Permission keys si sahihi: {sorted(bad)}. "
                f"Zinazoruhusiwa: {sorted(self.VALID_PERMISSIONS)}"
            )
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["label"] = {"sw": instance.label_sw, "en": instance.label_en}
        data["description"] = {
            "sw": instance.description_sw,
            "en": instance.description_en,
        }
        return data

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
    role_label = serializers.SerializerMethodField()
    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    def get_role_label(self, obj):
        return {"sw": obj.role.label_sw, "en": obj.role.label_en}

    class Meta:
        model = StaffAssignment
        fields = [
            "id", "user", "name", "email",
            "role", "role_key", "role_label", "active", "added_at",
        ]
        read_only_fields = ["id", "name", "email", "role_key", "role_label", "added_at"]


class StaffCreateSerializer(serializers.Serializer):
    user = serializers.IntegerField(required=False)
    role = serializers.IntegerField(required=False)
    user_id = serializers.IntegerField(required=False)
    role_key = serializers.CharField(max_length=60, required=False)
    active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        user_id = attrs.get("user") or attrs.get("user_id")
        if not user_id:
            raise serializers.ValidationError({"user": "user inahitajika."})
        attrs["user_id"] = user_id

        role_id = attrs.get("role")
        role_key = attrs.get("role_key")
        if not role_id and not role_key:
            raise serializers.ValidationError({"role": "role inahitajika."})
        if role_id:
            from .models import Role
            try:
                r = Role.objects.get(pk=role_id)
                attrs["role_key"] = r.key
            except Role.DoesNotExist:
                raise serializers.ValidationError({"role": "Role haipatikani."})
        return attrs


