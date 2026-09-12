
from rest_framework import serializers

from .models import BoostPackage, ListingBoost


# ============================================================================
# BOOST PACKAGE
# ============================================================================

class BoostPackageSerializer(serializers.ModelSerializer):
    duration_days = serializers.SerializerMethodField()

    class Meta:
        model = BoostPackage
        fields = [
            "id",
            "name",
            "duration_hours",
            "duration_days",
            "price",
            "description",
            "is_active",
            "ordering",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "duration_days",
            "created_at",
            "updated_at",
        ]

    def get_duration_days(self, obj):
        return obj.duration_hours / 24


# ============================================================================
# LISTING BOOST
# ============================================================================

class ListingBoostSerializer(serializers.ModelSerializer):
    package_name = serializers.CharField(
        source="package.name",
        read_only=True,
    )

    duration_hours = serializers.IntegerField(
        source="package.duration_hours",
        read_only=True,
    )

    duration_days = serializers.SerializerMethodField()

    listing_title = serializers.CharField(
        source="listing.title",
        read_only=True,
    )

    seller_name = serializers.CharField(
        source="seller.name",
        read_only=True,
    )

    class Meta:
        model = ListingBoost
        fields = [
            "id",
            "listing",
            "listing_title",
            "seller",
            "seller_name",
            "package",
            "package_name",
            "duration_hours",
            "duration_days",
            "amount",
            "payment_status",
            "payment_reference",
            "paid_at",
            "status",
            "starts_at",
            "expires_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "listing",
            "listing_title",
            "seller",
            "seller_name",
            "package_name",
            "duration_hours",
            "duration_days",
            "amount",
            "payment_status",
            "payment_reference",
            "paid_at",
            "status",
            "starts_at",
            "expires_at",
            "created_at",
            "updated_at",
        ]

    def get_duration_days(self, obj):
        return obj.package.duration_hours / 24


# ============================================================================
# CREATE BOOST
# ============================================================================

class BoostCreateSerializer(serializers.Serializer):
    listing = serializers.IntegerField(
        min_value=1,
    )

    package = serializers.PrimaryKeyRelatedField(
        queryset=BoostPackage.objects.filter(is_active=True),
    )

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None

        if not user or not user.is_authenticated:
            raise serializers.ValidationError(
                "Lazima uwe umeingia kwenye akaunti."
            )

        return attrs


# ============================================================================
# BOOST PAYMENT
# ============================================================================

class BoostPaymentSerializer(serializers.Serializer):
    payment_reference = serializers.CharField(
        max_length=255,
        allow_blank=False,
        trim_whitespace=True,
    )


# ============================================================================
# CANCEL BOOST
# ============================================================================

class BoostCancelSerializer(serializers.Serializer):
    confirm = serializers.BooleanField(
        required=True,
    )

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "Weka confirm=true ili ku-cancel boost."
            )

        return value
