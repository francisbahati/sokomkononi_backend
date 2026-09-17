from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.categories.models import Category
from apps.core.models import SoftDeleteModel


# ============================================================================
# LISTING
# ============================================================================

class Listing(SoftDeleteModel):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        AVAILABLE = "AVAILABLE", "Available"
        RESERVED = "RESERVED", "Reserved"
        SOLD = "SOLD", "Sold"
        REJECTED = "REJECTED", "Rejected"
        ARCHIVED = "ARCHIVED", "Archived"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listings",
        verbose_name="Muuzaji",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="listings",
        verbose_name="Kundi",
    )

    title = models.CharField(
        max_length=200,
        verbose_name="Jina la mali",
    )

    description = models.TextField(
        verbose_name="Maelezo",
    )

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Bei",
    )

    location = models.CharField(
        max_length=255,
        verbose_name="Mahali",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Hali",
    )

    is_featured = models.BooleanField(
        default=False,
        verbose_name="Imewekwa kwenye featured",
    )

    is_boosted = models.BooleanField(
        default=False,
        verbose_name="Imeboostiwa",
    )

    boosted_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Boost inaisha",
    )

    views_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Idadi ya kutazamwa",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Imeundwa",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Imesasishwa",
    )

    # =========================================================================
    # MODERATION
    # =========================================================================

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_listings",
        verbose_name="Imeidhinishwa na",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Muda wa kuidhinishwa",
    )

    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_listings",
        verbose_name="Imekataliwa na",
    )

    rejected_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Muda wa kukataliwa",
    )

    rejection_reason = models.TextField(
        blank=True,
        verbose_name="Sababu ya kukataliwa",
    )

    class Meta:
        db_table = "listings"
        ordering = ["-created_at"]

        verbose_name = "Tangazo"
        verbose_name_plural = "Matangazo"

        base_manager_name = "all_objects"
        default_manager_name = "objects"

        indexes = [
            models.Index(
                fields=["category", "status"],
                name="listing_category_status_idx",
            ),
            models.Index(
                fields=["seller", "status"],
                name="listing_seller_status_idx",
            ),
            models.Index(
                fields=["status", "created_at"],
                name="listing_status_created_idx",
            ),
        ]

    def __str__(self):
        return self.title


# ============================================================================
# LISTING IMAGE
# ============================================================================

class ListingImage(models.Model):

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="Tangazo",
    )

    image = models.ImageField(
        upload_to="listings/",
        verbose_name="Picha",
    )

    is_primary = models.BooleanField(
        default=False,
        verbose_name="Ni picha kuu",
    )

    ordering = models.PositiveIntegerField(
        default=0,
        verbose_name="Mpangilio",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Imeundwa",
    )

    class Meta:
        db_table = "listing_images"
        ordering = ["ordering", "created_at"]

        verbose_name = "Picha ya tangazo"
        verbose_name_plural = "Picha za matangazo"

        indexes = [
            models.Index(
                fields=["listing", "is_primary"],
                name="listing_image_primary_idx",
            ),
        ]

    def __str__(self):
        return f"{self.listing.title} - Image {self.pk}"


# ============================================================================
# PROPERTY DETAILS
# ============================================================================

class PropertyDetails(models.Model):

    class PropertyType(models.TextChoices):
        HOUSE = "HOUSE", "Nyumba"
        APARTMENT = "APARTMENT", "Apartment"
        OFFICE = "OFFICE", "Ofisi"
        SHOP = "SHOP", "Duka"
        WAREHOUSE = "WAREHOUSE", "Ghala"
        HOTEL = "HOTEL", "Hoteli"
        OTHER = "OTHER", "Nyingine"

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="property_details",
        verbose_name="Tangazo",
    )

    property_type = models.CharField(
        max_length=30,
        choices=PropertyType.choices,
        verbose_name="Aina ya jengo",
    )

    bedrooms = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Vyumba vya kulala",
    )

    bathrooms = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Vyumba vya kuogea",
    )

    floors = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Idadi ya ghorofa",
    )

    area_sqm = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Ukubwa (m²)",
    )

    furnished = models.BooleanField(
        default=False,
        verbose_name="Ina samani",
    )

    has_electricity = models.BooleanField(
        default=True,
        verbose_name="Ina umeme",
    )

    has_water = models.BooleanField(
        default=True,
        verbose_name="Ina maji",
    )

    has_parking = models.BooleanField(
        default=False,
        verbose_name="Ina maegesho",
    )

    ownership_document = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Aina ya hati ya umiliki",
    )

    class Meta:
        db_table = "property_details"
        verbose_name = "Maelezo ya nyumba/jengo"
        verbose_name_plural = "Maelezo ya nyumba/majengo"

    def __str__(self):
        return f"Property: {self.listing.title}"


# ============================================================================
# LAND DETAILS
# ============================================================================

class LandDetails(models.Model):

    class LandType(models.TextChoices):
        PLOT = "PLOT", "Kiwanja"
        FARM = "FARM", "Shamba"
        AGRICULTURAL = "AGRICULTURAL", "Ardhi ya kilimo"
        COMMERCIAL = "COMMERCIAL", "Ardhi ya biashara"
        RESIDENTIAL = "RESIDENTIAL", "Ardhi ya makazi"
        OTHER = "OTHER", "Nyingine"

    class SizeUnit(models.TextChoices):
        SQM = "SQM", "Mita za mraba"
        ACRE = "ACRE", "Ekari"
        HECTARE = "HECTARE", "Hekta"

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="land_details",
        verbose_name="Tangazo",
    )

    land_type = models.CharField(
        max_length=30,
        choices=LandType.choices,
        verbose_name="Aina ya ardhi",
    )

    size = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Ukubwa",
    )

    size_unit = models.CharField(
        max_length=15,
        choices=SizeUnit.choices,
        verbose_name="Kipimo cha ukubwa",
    )

    region = models.CharField(
        max_length=100,
        verbose_name="Mkoa",
    )

    district = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Wilaya",
    )

    ward = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Kata",
    )

    village_or_street = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Kijiji/Mtaa",
    )

    title_document = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Aina ya hati",
    )

    surveyed = models.BooleanField(
        default=False,
        verbose_name="Imepimwa",
    )

    road_access = models.BooleanField(
        default=True,
        verbose_name="Ina njia ya barabara",
    )

    electricity_nearby = models.BooleanField(
        default=False,
        verbose_name="Umeme upo karibu",
    )

    water_nearby = models.BooleanField(
        default=False,
        verbose_name="Maji yapo karibu",
    )

    class Meta:
        db_table = "land_details"
        verbose_name = "Maelezo ya ardhi"
        verbose_name_plural = "Maelezo ya ardhi"

    def __str__(self):
        return f"Land: {self.listing.title}"


# ============================================================================
# VEHICLE DETAILS
# ============================================================================

class VehicleDetails(models.Model):

    class VehicleType(models.TextChoices):
        CAR = "CAR", "Gari"
        SUV = "SUV", "SUV"
        PICKUP = "PICKUP", "Pickup"
        VAN = "VAN", "Van"
        TRUCK = "TRUCK", "Lori"
        BUS = "BUS", "Basi"
        MOTORCYCLE = "MOTORCYCLE", "Pikipiki"
        OTHER = "OTHER", "Nyingine"

    class FuelType(models.TextChoices):
        PETROL = "PETROL", "Petrol"
        DIESEL = "DIESEL", "Diesel"
        HYBRID = "HYBRID", "Hybrid"
        ELECTRIC = "ELECTRIC", "Electric"
        OTHER = "OTHER", "Nyingine"

    class Transmission(models.TextChoices):
        AUTOMATIC = "AUTOMATIC", "Automatic"
        MANUAL = "MANUAL", "Manual"
        SEMI_AUTOMATIC = "SEMI_AUTOMATIC", "Semi-Automatic"

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="vehicle_details",
        verbose_name="Tangazo",
    )

    make = models.CharField(
        max_length=100,
        verbose_name="Manufacturer",
    )

    model = models.CharField(
        max_length=100,
        verbose_name="Model",
    )

    year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Mwaka",
    )

    vehicle_type = models.CharField(
        max_length=30,
        choices=VehicleType.choices,
        verbose_name="Aina ya gari",
    )

    fuel_type = models.CharField(
        max_length=20,
        choices=FuelType.choices,
        verbose_name="Aina ya mafuta",
    )

    transmission = models.CharField(
        max_length=30,
        choices=Transmission.choices,
        verbose_name="Transmission",
    )

    mileage_km = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Mileage (km)",
    )

    engine_capacity_cc = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Engine capacity (cc)",
    )

    color = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Rangi",
    )

    seats = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Viti",
    )

    registration_number = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Namba ya usajili",
    )

    has_logbook = models.BooleanField(
        default=False,
        verbose_name="Ina logbook",
    )

    has_valid_insurance = models.BooleanField(
        default=False,
        verbose_name="Ina bima halali",
    )

    class Meta:
        db_table = "vehicle_details"
        verbose_name = "Maelezo ya gari"
        verbose_name_plural = "Maelezo ya magari"

    def __str__(self):
        return f"Vehicle: {self.listing.title}"


# ============================================================================
# BUSINESS DETAILS
# ============================================================================

class BusinessDetails(models.Model):

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="business_details",
        verbose_name="Tangazo",
    )

    business_type = models.CharField(
        max_length=100,
        verbose_name="Aina ya biashara",
    )

    years_operating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Miaka ya biashara",
    )

    number_of_employees = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Idadi ya wafanyakazi",
    )

    monthly_revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Mapato ya mwezi",
    )

    monthly_expenses = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Gharama za mwezi",
    )

    has_business_license = models.BooleanField(
        default=False,
        verbose_name="Ina leseni ya biashara",
    )

    has_tin = models.BooleanField(
        default=False,
        verbose_name="Ina TIN",
    )

    premises_included = models.BooleanField(
        default=False,
        verbose_name="Eneo la biashara linajumuishwa",
    )

    stock_included = models.BooleanField(
        default=False,
        verbose_name="Stock inajumuishwa",
    )

    reason_for_sale = models.TextField(
        blank=True,
        verbose_name="Sababu ya kuuza",
    )

    class Meta:
        db_table = "business_details"
        verbose_name = "Maelezo ya biashara"
        verbose_name_plural = "Maelezo ya biashara"

    def __str__(self):
        return f"Business: {self.listing.title}"


# ============================================================================
# EQUIPMENT DETAILS
# ============================================================================

class EquipmentDetails(models.Model):

    class Condition(models.TextChoices):
        NEW = "NEW", "Mpya"
        USED = "USED", "Imetumika"
        REFURBISHED = "REFURBISHED", "Imerekebishwa"

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="equipment_details",
        verbose_name="Tangazo",
    )

    equipment_type = models.CharField(
        max_length=100,
        verbose_name="Aina ya mashine",
    )

    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Manufacturer",
    )

    model = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Model",
    )

    year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Mwaka",
    )

    condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        verbose_name="Hali ya mashine",
    )

    operating_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Masaa ya matumizi",
    )

    fuel_type = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Aina ya mafuta",
    )

    engine_capacity = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Engine capacity",
    )

    weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Uzito (kg)",
    )

    serial_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Serial number",
    )

    country_of_origin = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nchi ilikotoka",
    )

    class Meta:
        db_table = "equipment_details"
        verbose_name = "Maelezo ya mashine"
        verbose_name_plural = "Maelezo ya mashine"

    def __str__(self):
        return f"Equipment: {self.listing.title}"


# ============================================================================
# LISTING FEE (financial — NOT soft-deletable)
# ============================================================================

class ListingFee(models.Model):

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Inasubiri Malipo"
        PAID = "PAID", "Imelipwa"
        FAILED = "FAILED", "Imeshindikana"
        REFUNDED = "REFUNDED", "Imerejeshwa"

    listing = models.OneToOneField(
        Listing,
        on_delete=models.CASCADE,
        related_name="listing_fee",
        verbose_name="Tangazo",
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="listing_fees",
        verbose_name="Muuzaji",
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Kiasi cha ada",
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        verbose_name="Hali ya malipo",
    )

    payment_reference = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        unique=True,
        verbose_name="Namba ya kumbukumbu ya malipo",
    )

    paid_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Tarehe ya malipo",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Imeundwa",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Imesasishwa",
    )

    class Meta:
        db_table = "listing_fees"
        ordering = ["-created_at"]

        verbose_name = "Ada ya tangazo"
        verbose_name_plural = "Ada za matangazo"

        indexes = [
            models.Index(
                fields=["seller", "payment_status"],
                name="listing_fee_seller_status_idx",
            ),
            models.Index(
                fields=["payment_status"],
                name="listing_fee_payment_status_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.listing.title} - "
            f"{self.amount} - "
            f"{self.payment_status}"
        )


# ============================================================================
# LISTING FEE RULE
# ============================================================================

class ListingFeeRule(SoftDeleteModel):

    name = models.CharField(
        max_length=100,
        verbose_name="Jina la kiwango",
    )

    min_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Bei ya chini",
    )

    max_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Bei ya juu",
        help_text="Acha wazi kwa kiwango kisicho na mwisho wa juu.",
    )

    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Asilimia ya ada",
        help_text="Mfano: 2.50 kwa 2.5%",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Inatumika",
    )

    priority = models.PositiveIntegerField(
        default=0,
        verbose_name="Kipaumbele",
        help_text="Namba ndogo hupewa kipaumbele cha kwanza.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "listing_fee_rules"
        ordering = ["priority", "min_price"]

        verbose_name = "Kanuni ya ada ya tangazo"
        verbose_name_plural = "Kanuni za ada za matangazo"

        base_manager_name = "all_objects"
        default_manager_name = "objects"

        indexes = [
            models.Index(
                fields=["is_active", "priority"],
                name="fee_rule_active_prio_idx",
            ),
        ]

    def __str__(self):
        if self.max_price is None:
            price_range = f"TSh {self.min_price}+"
        else:
            price_range = (
                f"TSh {self.min_price} - {self.max_price}"
            )

        return (
            f"{self.name} "
            f"({price_range}) - "
            f"{self.percentage}%"
        )