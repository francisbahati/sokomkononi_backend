from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import User
from apps.listings.models import Listing

from .models import DealRoom, NegotiationOffer


# ============================================================================
# BASIC / NESTED SERIALIZERS
# ============================================================================

class DealListingSerializer(serializers.ModelSerializer):
    """
    Maelezo mafupi ya tangazo yanayoonekana ndani ya Deal Room.
    """

    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
    )

    class Meta:
        model = Listing
        fields = [
            "id",
            "title",
            "description",
            "price",
            "location",
            "status",
            "category_name",
        ]
        read_only_fields = fields


class DealUserSerializer(serializers.ModelSerializer):
    """
    Maelezo machache ya mtumiaji ndani ya Deal Room.
    """

    class Meta:
        model = User
        fields = [
            "id",
            "name",
        ]
        read_only_fields = fields


# ============================================================================
# NEGOTIATION OFFER SERIALIZERS
# ============================================================================

class NegotiationOfferSerializer(serializers.ModelSerializer):
    """
    Huonyesha offer moja pamoja na taarifa za aliyetoa.
    """

    offered_by_name = serializers.CharField(
        source="offered_by.name",
        read_only=True,
    )

    offered_by_role = serializers.SerializerMethodField()

    responded_to_id = serializers.IntegerField(
        source="responded_to.id",
        read_only=True,
    )

    class Meta:
        model = NegotiationOffer
        fields = [
            "id",
            "deal_room",
            "offered_by",
            "offered_by_name",
            "offered_by_role",
            "amount",
            "message",
            "status",
            "responded_to_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "deal_room",
            "offered_by",
            "offered_by_name",
            "offered_by_role",
            "status",
            "responded_to_id",
            "created_at",
            "updated_at",
        ]

    def get_offered_by_role(self, obj):
        if obj.offered_by_id == obj.deal_room.buyer_id:
            return "BUYER"

        if obj.offered_by_id == obj.deal_room.seller_id:
            return "SELLER"

        return None


class NegotiationOfferCreateSerializer(serializers.Serializer):
    """
    Serializer ya kutuma offer mpya au counter-offer.
    """

    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal("0.01"),
        help_text="Kiasi cha offer kwa TZS.",
    )

    message = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        help_text="Ujumbe wa ziada kwa upande mwingine.",
    )

    responded_to = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="ID ya offer ambayo offer hii inajibu.",
    )

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError(
                "Kiasi cha offer lazima kiwe zaidi ya sifuri."
            )

        return value

    def validate_responded_to(self, value):
        if value is None:
            return value

        deal_room = self.context.get("deal_room")

        if not deal_room:
            return value

        try:
            offer = NegotiationOffer.objects.get(
                pk=value,
                deal_room=deal_room,
            )
        except NegotiationOffer.DoesNotExist:
            raise serializers.ValidationError(
                "Offer uliyochagua haipo kwenye Deal Room hii."
            )

        if offer.status == NegotiationOffer.Status.CANCELLED:
            raise serializers.ValidationError(
                "Huwezi kujibu offer iliyofutwa."
            )

        return value

    def validate(self, attrs):
        deal_room = self.context.get("deal_room")
        request = self.context.get("request")

        if not deal_room:
            raise serializers.ValidationError(
                "Deal Room haijapatikana."
            )

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Ni lazima uwe umeingia kwenye akaunti."
            )

        if deal_room.status not in [
            DealRoom.Status.OPEN,
            DealRoom.Status.NEGOTIATING,
        ]:
            raise serializers.ValidationError(
                "Deal Room hii haipokei offers mpya."
            )

        if request.user.id not in [
            deal_room.buyer_id,
            deal_room.seller_id,
        ]:
            raise serializers.ValidationError(
                "Huruhusiwi kutuma offer kwenye Deal Room hii."
            )

        responded_to_id = attrs.get("responded_to")

        if responded_to_id:
            responded_to = NegotiationOffer.objects.get(
                pk=responded_to_id,
                deal_room=deal_room,
            )

            if responded_to.offered_by_id == request.user.id:
                raise serializers.ValidationError(
                    {
                        "responded_to": (
                            "Huwezi kujibu offer yako mwenyewe."
                        )
                    }
                )

            if responded_to.status in [
                NegotiationOffer.Status.ACCEPTED,
                NegotiationOffer.Status.REJECTED,
                NegotiationOffer.Status.CANCELLED,
            ]:
                raise serializers.ValidationError(
                    {
                        "responded_to": (
                            "Offer hii haiwezi kujibiwa tena."
                        )
                    }
                )

        return attrs


# ============================================================================
# DEAL ROOM SERIALIZERS
# ============================================================================

class DealRoomListSerializer(serializers.ModelSerializer):
    """
    Serializer nyepesi kwa orodha ya Deal Rooms.
    """

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

    buyer_name = serializers.CharField(
        source="buyer.name",
        read_only=True,
    )

    seller_name = serializers.CharField(
        source="seller.name",
        read_only=True,
    )

    latest_offer = serializers.SerializerMethodField()

    class Meta:
        model = DealRoom
        fields = [
            "id",
            "listing",
            "listing_title",
            "listing_price",
            "buyer",
            "buyer_name",
            "seller",
            "seller_name",
            "status",
            "agreed_price",
            "agreed_at",
            "latest_offer",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_latest_offer(self, obj):
        offer = (
            obj.offers
            .select_related("offered_by")
            .order_by("-created_at")
            .first()
        )

        if not offer:
            return None

        return NegotiationOfferSerializer(
            offer,
            context=self.context,
        ).data


class DealRoomDetailSerializer(serializers.ModelSerializer):
    """
    Serializer kamili ya Deal Room pamoja na negotiation history.
    """

    listing = DealListingSerializer(
        read_only=True,
    )

    buyer = DealUserSerializer(
        read_only=True,
    )

    seller = DealUserSerializer(
        read_only=True,
    )

    offers = NegotiationOfferSerializer(
        many=True,
        read_only=True,
    )

    offer_count = serializers.SerializerMethodField()

    latest_offer = serializers.SerializerMethodField()

    class Meta:
        model = DealRoom
        fields = [
            "id",
            "listing",
            "buyer",
            "seller",
            "status",
            "agreed_price",
            "agreed_at",
            "offers",
            "offer_count",
            "latest_offer",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_offer_count(self, obj):
        return obj.offers.count()

    def get_latest_offer(self, obj):
        offer = (
            obj.offers
            .select_related("offered_by")
            .order_by("-created_at")
            .first()
        )

        if not offer:
            return None

        return NegotiationOfferSerializer(
            offer,
            context=self.context,
        ).data


class DealRoomCreateSerializer(serializers.Serializer):
    """
    Serializer ya kuanzisha Deal Room.

    Buyer anatoa listing ID tu.
    Seller anapatikana kutoka kwenye Listing yenyewe.
    """

    listing_id = serializers.IntegerField(
        required=True,
        help_text="ID ya tangazo ambalo mnunuzi anataka kununua.",
    )

    def validate_listing_id(self, value):
        try:
            listing = (
                Listing.objects
                .select_related(
                    "seller",
                    "category",
                )
                .get(pk=value)
            )
        except Listing.DoesNotExist:
            raise serializers.ValidationError(
                "Tangazo halijapatikana."
            )

        if listing.status != Listing.Status.AVAILABLE:
            raise serializers.ValidationError(
                "Deal Room inaweza kuanzishwa kwa tangazo "
                "lililo AVAILABLE pekee."
            )

        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Ni lazima uwe umeingia kwenye akaunti."
            )

        if listing.seller_id == request.user.id:
            raise serializers.ValidationError(
                "Huwezi kuanzisha Deal Room kwenye tangazo lako mwenyewe."
            )

        existing = DealRoom.objects.filter(
            listing=listing,
            buyer=request.user,
        ).first()

        if existing:
            raise serializers.ValidationError(
                {
                    "listing_id": (
                        f"Deal Room tayari ipo kwa tangazo hili. "
                        f"Deal Room ID: {existing.id}"
                    )
                }
            )

        return value

    def create(self, validated_data):
        request = self.context["request"]

        listing = (
            Listing.objects
            .select_related("seller")
            .get(pk=validated_data["listing_id"])
        )

        return DealRoom.objects.create(
            listing=listing,
            seller=listing.seller,
            buyer=request.user,
            status=DealRoom.Status.OPEN,
        )


# ============================================================================
# DEAL ROOM STATUS ACTION SERIALIZERS
# ============================================================================

class DealRoomCancelSerializer(serializers.Serializer):
    """
    Serializer ya kufunga Deal Room.
    """

    reason = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        max_length=500,
        help_text="Sababu ya kufunga Deal Room.",
    )

    def validate_reason(self, value):
        return value.strip()


class DealRoomAcceptOfferSerializer(serializers.Serializer):
    """
    Serializer ya kukubali offer.
    """

    offer_id = serializers.IntegerField(
        required=True,
        help_text="ID ya offer inayokubaliwa.",
    )

    def validate_offer_id(self, value):
        deal_room = self.context.get("deal_room")

        if not deal_room:
            raise serializers.ValidationError(
                "Deal Room haijapatikana."
            )

        try:
            offer = NegotiationOffer.objects.get(
                pk=value,
                deal_room=deal_room,
            )
        except NegotiationOffer.DoesNotExist:
            raise serializers.ValidationError(
                "Offer haijapatikana kwenye Deal Room hii."
            )

        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Ni lazima uwe umeingia kwenye akaunti."
            )

        if request.user.id not in [
            deal_room.buyer_id,
            deal_room.seller_id,
        ]:
            raise serializers.ValidationError(
                "Huruhusiwi kukubali offer kwenye Deal Room hii."
            )

        if offer.offered_by_id == request.user.id:
            raise serializers.ValidationError(
                "Huwezi kukubali offer yako mwenyewe."
            )

        if offer.status != NegotiationOffer.Status.PENDING:
            raise serializers.ValidationError(
                "Offer hii haiwezi kukubaliwa kwa sababu hali yake si PENDING."
            )

        if deal_room.status not in [
            DealRoom.Status.OPEN,
            DealRoom.Status.NEGOTIATING,
        ]:
            raise serializers.ValidationError(
                "Deal Room hii haiwezi kukubali offer."
            )

        return value