from rest_framework import serializers

from .models import UserCredit, UserService


class UserCreditSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserCredit
        fields = [
            "id", "service_key", "remaining", "total",
            "expires_at", "last_bundle_code", "last_bundle_name",
            "updated_at",
        ]
        read_only_fields = fields


class UserServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserService
        fields = ["id", "service_key", "expires_at", "granted_at"]
        read_only_fields = fields


class ConsumeCreditSerializer(serializers.Serializer):
    service_key = serializers.CharField(max_length=50)
    amount = serializers.IntegerField(min_value=1, default=1)
