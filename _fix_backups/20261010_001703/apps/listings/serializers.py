from rest_framework import serializers

from apps.categories.models import Category

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
        model = Category
        fields = [
            "id",
            "name",
            "slug",
        ]


# ============================================================================
# HELPER — seller contact visibility
# ============================================================================

def _seller_contact_visible(request, seller, field_name):
    """
    Rudisha True kama mwombaji anaruhusiwa kuona contact ya seller.

    field_name: "phone" au "email".

    Sheria:
      - Mmiliki (seller mwenyewe) — ona kila kitu
      - Staff — ona kila kitu
      - Wengine — ona TU kama seller.preferences.show_{field_name} == True
        (au kama hakuna prefs, default ni kuonyesha)
    """
    if not seller:
        return False

    if request and request.user.is_authenticated:
        if request.user.id == seller.id or request.user.is_staff:
            return True

    try:
        prefs = seller.preferences
        if field_name == "phone" and not prefs.show_phone:
            return False
        if field_name == "email" and not prefs.show_email:
            return False
    except Exception:
        pass

    return True


# ============================================================================
# LISTING LIST
# ============================================================================

class ListingListSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(
        source="seller.name",
        read_only=True,
    )

    seller_phone = serializers.SerializerMethodField()
    seller_email = serializers.SerializerMethodField()

    category = ListingCategorySerializer(
        read_only=True,
    )

    primary_image = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    payment_label = serializers.SerializerMethodField()
    fee_amount = serializers.SerializerMethodField()
    is_paid = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    leading_expires_at = serializers.DateTimeField(
        source="leading_until", read_only=True,
    )

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "price",
            "location",
            "attributes",
            "status",
            "status_label",
            "payment_status",
            "payment_label",
            "fee_amount",
            "is_paid",
            "payment_status",
            "leading_expires_at",
            "is_featured",
            "is_boosted",
            "views_count",
            "seller_name",
            "seller_phone",
            "seller_email",
            "category",
            "primary_image",
            "created_at",
        ]

    def get_seller_phone(self, obj):
        request = self.context.get("request")
        if not _seller_contact_visible(request, obj.seller, "phone"):
            return None
        return getattr(obj.seller, "phone", None)

    def get_seller_email(self, obj):
        request = self.context.get("request")
        if not _seller_contact_visible(request, obj.seller, "email"):
            return None
        return getattr(obj.seller, "email", None)

    def get_status_label(self, obj):
        labels = {
            "DRAFT": "Rasimu",
            "PENDING_PAYMENT": "Haijalipwa",
            "PENDING_APPROVAL": "Inasubiri idhini",
            "LIVE": "Hai",
            "RESERVED": "Imehifadhiwa",
            "SOLD": "Imeuzwa",
            "PAUSED": "Imesimamishwa",
            "REJECTED": "Imekataliwa",
            "EXPIRED": "Imeisha muda",
            "ARCHIVED": "Kumbukumbu",
        }
        return labels.get(obj.status, obj.status)

    def get_payment_status(self, obj):
        fee = getattr(obj, "listing_fee", None)
        return fee.payment_status if fee else "PENDING"

    def get_payment_label(self, obj):
        fee = getattr(obj, "listing_fee", None)
        if fee is None:
            return "Haijalipwa"
        labels = {
            "PENDING": "Haijalipwa",
            "PAID": "Imelipwa",
            "FAILED": "Imeshindikana",
            "REFUNDED": "Imerejeshwa",
        }
        return labels.get(fee.payment_status, fee.payment_status)

    def get_fee_amount(self, obj):
        fee = getattr(obj, "listing_fee", None)
        return str(fee.amount) if fee else None

    def get_is_paid(self, obj):
        fee = getattr(obj, "listing_fee", None)
        if fee is None:
            return False
        return fee.payment_status == "PAID"

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

    seller_phone = serializers.SerializerMethodField()
    seller_email = serializers.SerializerMethodField()

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

    fee_required = serializers.SerializerMethodField()
    fee_amount = serializers.SerializerMethodField()
    fee_status = serializers.SerializerMethodField()
    is_paid = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    leading_expires_at = serializers.DateTimeField(
        source="leading_until", read_only=True,
    )

    class Meta:
        model = Listing
        fields = [
            "id",
            "seller",
            "seller_name",
            "seller_phone",
            "seller_email",
            "category",
            "title",
            "description",
            "price",
            "location",
            "attributes",
            "fee_required",
            "fee_amount",
            "fee_status",
            "is_paid",
            "payment_status",
            "seller",
            "leading_expires_at",
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
            "seller_phone",
            "seller_email",
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

    def get_seller_phone(self, obj):
        request = self.context.get("request")
        if not _seller_contact_visible(request, obj.seller, "phone"):
            return None
        return getattr(obj.seller, "phone", None)

    def get_seller_email(self, obj):
        request = self.context.get("request")
        if not _seller_contact_visible(request, obj.seller, "email"):
            return None
        return getattr(obj.seller, "email", None)

    def get_fee_required(self, obj):
        from .services.listing_moderation import _is_listing_fee_required_for
        try:
            return _is_listing_fee_required_for(obj)
        except Exception:
            return False

    def get_fee_amount(self, obj):
        fee = getattr(obj, "listing_fee", None)
        if fee is None:
            try:
                from .services.listing_fee import calculate_listing_fee
                cat = obj.category if obj.category_id else None
                slug = getattr(cat, "slug", None)
                result = calculate_listing_fee(
                    obj.price, category_slug=slug, category=cat,
                )
                return str(result["fee_amount"])
            except Exception:
                return None
        return str(fee.amount)

    def get_fee_status(self, obj):
        fee = getattr(obj, "listing_fee", None)
        return fee.payment_status if fee else "PENDING"

    def get_is_paid(self, obj):
        fee = getattr(obj, "listing_fee", None)
        return bool(fee and fee.payment_status == "PAID")

    def get_payment_status(self, obj):
        fee = getattr(obj, "listing_fee", None)
        return fee.payment_status if fee else "PENDING"

    def get_seller(self, obj):
        u = getattr(obj, "seller", None)
        if not u:
            return None
        return {"id": u.id, "name": getattr(u, "name", "") or ""}

    def get_payment_status(self, obj):
        fee = getattr(obj, "listing_fee", None)
        return fee.payment_status if fee else "PENDING"

    def get_seller(self, obj):
        s = getattr(obj, "seller", None)
        if not s:
            return None
        return {"id": s.id, "name": getattr(s, "name", "") or ""}


# ============================================================================
# LISTING WRITE
# ============================================================================

class ListingWriteSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True),
        required=True,
        write_only=True,
    )

    class Meta:
        model = Listing
        fields = [
            "category",
            "title",
            "description",
            "price",
            "location",
            "attributes",
        ]

    def to_internal_value(self, data):
        try:
            normalized = data.copy()
        except AttributeError:
            normalized = dict(data)

        if "category_id" in normalized and "category" not in normalized:
            normalized["category"] = normalized["category_id"]

        normalized.pop("category_id", None)

        return super().to_internal_value(normalized)

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

    def validate_attributes(self, value):
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "Attributes lazima iwe JSON object."
            )
        return value


class ListingFeeSerializer(serializers.ModelSerializer):
    listing_id = serializers.IntegerField(
        source="listing.id",
        read_only=True,
    )

    currency = serializers.SerializerMethodField()
    is_disabled = serializers.SerializerMethodField()
    amount_display = serializers.SerializerMethodField()
    pay_endpoint = serializers.SerializerMethodField()
    fee_amount = serializers.DecimalField(
        source="amount",
        max_digits=15,
        decimal_places=2,
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
            "fee_amount",
            "amount_display",
            "currency",
            "is_disabled",
            "pay_endpoint",
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
            "fee_amount",
            "amount_display",
            "currency",
            "is_disabled",
            "pay_endpoint",
            "payment_status",
            "payment_reference",
            "paid_at",
            "created_at",
            "updated_at",
        ]

    def get_fee_percentage(self, obj):
        return obj.percentage

    def get_currency(self, obj):
        return "TZS"

    def get_amount_display(self, obj):
        try:
            return f"TZS {obj.amount:,.0f}"
        except Exception:
            return f"TZS {obj.amount}"

    def get_pay_endpoint(self, obj):
        return f"/api/listings/{obj.listing_id}/fee/pay/"

    def get_is_disabled(self, obj):
        return False


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
            "attributes",
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

    def get_status_label(self, obj):
        labels = {
            "DRAFT": "Rasimu",
            "PENDING_PAYMENT": "Haijalipwa",
            "PENDING_APPROVAL": "Inasubiri idhini",
            "LIVE": "Hai",
            "RESERVED": "Imehifadhiwa",
            "SOLD": "Imeuzwa",
            "PAUSED": "Imesimamishwa",
            "REJECTED": "Imekataliwa",
            "EXPIRED": "Imeisha muda",
            "ARCHIVED": "Kumbukumbu",
        }
        return labels.get(obj.status, obj.status)

    def get_payment_status(self, obj):
        fee = getattr(obj, "listing_fee", None)
        return fee.payment_status if fee else "PENDING"

    def get_payment_label(self, obj):
        fee = getattr(obj, "listing_fee", None)
        if fee is None:
            return "Haijalipwa"
        labels = {
            "PENDING": "Haijalipwa",
            "PAID": "Imelipwa",
            "FAILED": "Imeshindikana",
            "REFUNDED": "Imerejeshwa",
        }
        return labels.get(fee.payment_status, fee.payment_status)

    def get_fee_amount(self, obj):
        fee = getattr(obj, "listing_fee", None)
        return str(fee.amount) if fee else None

    def get_is_paid(self, obj):
        fee = getattr(obj, "listing_fee", None)
        if fee is None:
            return False
        return fee.payment_status == "PAID"

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
        fee = getattr(obj, "listing_fee", None)
        return fee.payment_status if fee else None

    def get_fee_amount(self, obj):
        fee = getattr(obj, "listing_fee", None)
        return fee.amount if fee else None