from rest_framework import serializers

from .models import (
    BusinessDetails,
    EquipmentDetails,
    LandDetails,
    Listing,
    ListingFee,
    ListingImage,
    PropertyDetails,
    VehicleDetails,
)
from .services.listing_fee import calculate_listing_fee


# ============================================================================
# LISTING IMAGE
# ============================================================================

class ListingImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ListingImage
        fields = [
            "id",
            "image",
            "image_url",
            "is_primary",
            "ordering",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "image_url",
            "created_at",
        ]

    def get_image_url(self, obj):
        request = self.context.get("request")

        if not obj.image:
            return None

        url = obj.image.url

        if request:
            return request.build_absolute_uri(url)

        return url

    def validate_ordering(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Mpangilio hauwezi kuwa chini ya sifuri."
            )

        return value


# ============================================================================
# CATEGORY
# ============================================================================

class ListingCategorySerializer(serializers.ModelSerializer):
    class Meta:
        from apps.categories.models import Category

        model = Category
        fields = [
            "id",
            "name",
            "slug",
        ]


# ============================================================================
# LISTING LIST
# ============================================================================

class ListingListSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(
        source="seller.name",
        read_only=True,
    )

    category = ListingCategorySerializer(
        read_only=True,
    )

    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "price",
            "location",
            "status",
            "is_featured",
            "is_boosted",
            "views_count",
            "seller_name",
            "category",
            "primary_image",
            "created_at",
        ]

    def get_primary_image(self, obj):
        image = (
            obj.images
            .filter(is_primary=True)
            .first()
        )

        if not image:
            image = (
                obj.images
                .order_by(
                    "ordering",
                    "created_at",
                )
                .first()
            )

        if not image or not image.image:
            return None

        request = self.context.get("request")
        url = image.image.url

        if request:
            return request.build_absolute_uri(url)

        return url


# ============================================================================
# PROPERTY DETAILS
# ============================================================================

class PropertyDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyDetails
        fields = [
            "id",
            "listing",
            "property_type",
            "bedrooms",
            "bathrooms",
            "floors",
            "area_sqm",
            "furnished",
            "has_electricity",
            "has_water",
            "has_parking",
            "ownership_document",
        ]
        read_only_fields = [
            "id",
            "listing",
        ]


# ============================================================================
# LAND DETAILS
# ============================================================================

class LandDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LandDetails
        fields = [
            "id",
            "listing",
            "land_type",
            "size",
            "size_unit",
            "region",
            "district",
            "ward",
            "village_or_street",
            "title_document",
            "surveyed",
            "road_access",
            "electricity_nearby",
            "water_nearby",
        ]
        read_only_fields = [
            "id",
            "listing",
        ]


# ============================================================================
# VEHICLE DETAILS
# ============================================================================

class VehicleDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleDetails
        fields = [
            "id",
            "listing",
            "make",
            "model",
            "year",
            "vehicle_type",
            "fuel_type",
            "transmission",
            "mileage_km",
            "engine_capacity_cc",
            "color",
            "seats",
            "registration_number",
            "has_logbook",
            "has_valid_insurance",
        ]
        read_only_fields = [
            "id",
            "listing",
        ]


# ============================================================================
# BUSINESS DETAILS
# ============================================================================

class BusinessDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessDetails
        fields = [
            "id",
            "listing",
            "business_type",
            "years_operating",
            "number_of_employees",
            "monthly_revenue",
            "monthly_expenses",
            "has_business_license",
            "has_tin",
            "premises_included",
            "stock_included",
            "reason_for_sale",
        ]
        read_only_fields = [
            "id",
            "listing",
        ]


# ============================================================================
# EQUIPMENT DETAILS
# ============================================================================

class EquipmentDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentDetails
        fields = [
            "id",
            "listing",
            "equipment_type",
            "manufacturer",
            "model",
            "year",
            "condition",
            "operating_hours",
            "fuel_type",
            "engine_capacity",
            "weight_kg",
            "serial_number",
            "country_of_origin",
        ]
        read_only_fields = [
            "id",
            "listing",
        ]


# ============================================================================
# LISTING DETAIL
# ============================================================================

class ListingDetailSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(
        source="seller.name",
        read_only=True,
    )

    category = ListingCategorySerializer(
        read_only=True,
    )

    images = ListingImageSerializer(
        many=True,
        read_only=True,
    )

    property_details = PropertyDetailsSerializer(
        read_only=True,
    )

    land_details = LandDetailsSerializer(
        read_only=True,
    )

    vehicle_details = VehicleDetailsSerializer(
        read_only=True,
    )

    business_details = BusinessDetailsSerializer(
        read_only=True,
    )

    equipment_details = EquipmentDetailsSerializer(
        read_only=True,
    )

    class Meta:
        model = Listing
        fields = [
            "id",
            "seller",
            "seller_name",
            "category",
            "title",
            "description",
            "price",
            "location",
            "status",
            "is_featured",
            "is_boosted",
            "boosted_until",
            "views_count",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "images",
            "property_details",
            "land_details",
            "vehicle_details",
            "business_details",
            "equipment_details",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "seller",
            "seller_name",
            "category",
            "status",
            "is_featured",
            "is_boosted",
            "boosted_until",
            "views_count",
            "approved_by",
            "approved_at",
            "rejected_by",
            "rejected_at",
            "rejection_reason",
            "images",
            "property_details",
            "land_details",
            "vehicle_details",
            "business_details",
            "equipment_details",
            "created_at",
            "updated_at",
        ]


# ============================================================================
# LISTING WRITE
# ============================================================================

class ListingWriteSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=__import__(
            "apps.categories.models",
            fromlist=["Category"],
        ).Category.objects.filter(
            is_active=True
        ),
        write_only=True,
    )

    class Meta:
        model = Listing
        fields = [
            "category_id",
            "title",
            "description",
            "price",
            "location",
        ]

    def validate_title(self, value):
        value = value.strip()

        if len(value) < 5:
            raise serializers.ValidationError(
                "Jina la tangazo lazima liwe na angalau herufi 5."
            )

        return value

    def validate_description(self, value):
        value = value.strip()

        if len(value) < 20:
            raise serializers.ValidationError(
                "Maelezo ya tangazo lazima yawe na angalau herufi 20."
            )

        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Bei haiwezi kuwa chini ya sifuri."
            )

        return value

    def validate_location(self, value):
        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "Tafadhali weka eneo sahihi."
            )

        return value


# ============================================================================
# LISTING FEE SERIALIZER
# ============================================================================

class ListingFeeSerializer(serializers.ModelSerializer):
    listing_id = serializers.IntegerField(
        source="listing.id",
        read_only=True,
    )

    listing_title = serializers.CharField(
        source="listing.title",
        read_only=True,
    )

    listing_price = serializers.DecimalField(
        source="listing.price",
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )

    fee_percentage = serializers.SerializerMethodField()

    class Meta:
        model = ListingFee
        fields = [
            "id",
            "listing_id",
            "listing_title",
            "listing_price",
            "fee_percentage",
            "amount",
            "payment_status",
            "payment_reference",
            "paid_at",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "listing_id",
            "listing_title",
            "listing_price",
            "fee_percentage",
            "amount",
            "payment_status",
            "payment_reference",
            "paid_at",
            "created_at",
            "updated_at",
        ]

    def get_fee_percentage(self, obj):
        try:
            result = calculate_listing_fee(
                obj.listing.price
            )
            return result["percentage"]
        except Exception:
            return None


# ============================================================================
# LISTING FEE PAYMENT SERIALIZER
# ============================================================================

class ListingFeePaymentSerializer(serializers.Serializer):
    payment_reference = serializers.CharField(
        max_length=150,
        required=True,
        help_text="Namba ya kumbukumbu ya malipo.",
    )

    def validate_payment_reference(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Payment reference inahitajika."
            )

        return value


# ============================================================================
# LISTING MODERATION — REJECTION
# ============================================================================

class ListingRejectionSerializer(serializers.Serializer):
    rejection_reason = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True,
        help_text="Sababu ya kukataa tangazo.",
    )

    def validate_rejection_reason(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Sababu ya kukataa tangazo inahitajika."
            )

        if len(value) < 5:
            raise serializers.ValidationError(
                "Sababu ya kukataa lazima iwe na angalau herufi 5."
            )

        return value


# ============================================================================
# ADMIN PENDING LISTING
# ============================================================================

class AdminPendingListingSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(
        source="seller.name",
        read_only=True,
    )

    seller_email = serializers.CharField(
        source="seller.email",
        read_only=True,
    )

    category = ListingCategorySerializer(
        read_only=True,
    )

    primary_image = serializers.SerializerMethodField()

    fee_status = serializers.SerializerMethodField()

    fee_amount = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "description",
            "price",
            "location",
            "status",
            "seller",
            "seller_name",
            "seller_email",
            "category",
            "primary_image",
            "fee_status",
            "fee_amount",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields

    def get_primary_image(self, obj):
        image = (
            obj.images
            .filter(is_primary=True)
            .first()
        )

        if not image:
            image = (
                obj.images
                .order_by(
                    "ordering",
                    "created_at",
                )
                .first()
            )

        if not image or not image.image:
            return None

        request = self.context.get("request")
        url = image.image.url

        if request:
            return request.build_absolute_uri(url)

        return url

    def get_fee_status(self, obj):
        try:
            return obj.listing_fee.payment_status
        except ListingFee.DoesNotExist:
            return None

    def get_fee_amount(self, obj):
        try:
            return obj.listing_fee.amount
        except ListingFee.DoesNotExist:
            return None