from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import User
from apps.listings.models import Listing

from .models import DealRoom, NegotiationOffer


class DealListingSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Listing
        fields = [
            "id", "title", "description", "price", "location",
            "status", "category_name",
        ]
        read_only_fields = fields


class DealUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "name"]
        read_only_fields = fields


class NegotiationOfferSerializer(serializers.ModelSerializer):
    offered_by_name = serializers.CharField(
        source="offered_by.name", read_only=True,
    )
    offered_by_role = serializers.SerializerMethodField()
    responded_to_id = serializers.IntegerField(
        source="responded_to.id", read_only=True,
    )

    class Meta:
        model = NegotiationOffer
        fields = [
            "id", "deal_room", "offered_by", "offered_by_name",
            "offered_by_role", "amount", "message", "status",
            "responded_to_id", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "deal_room", "offered_by", "offered_by_name",
            "offered_by_role", "status", "responded_to_id",
            "created_at", "updated_at",
        ]

    def get_offered_by_role(self, obj):
        room = self.context.get("deal_room")
        if room is None:
            room = obj.deal_room
        if obj.offered_by_id == room.buyer_id:
            return "BUYER"
        if obj.offered_by_id == room.seller_id:
            return "SELLER"
        return None


class NegotiationOfferCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=Decimal("0.01"),
    )
    message = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=True,
    )
    responded_to = serializers.IntegerField(
        required=False, allow_null=True,
    )

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError(
                "Kiasi cha offer lazima kiwe zaidi ya sifuri."
            )
        return value

    def validate(self, attrs):
        deal_room = self.context.get("deal_room")
        request = self.context.get("request")

        if not deal_room:
            raise serializers.ValidationError("Deal Room haijapatikana.")
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
            try:
                offer = NegotiationOffer.objects.get(
                    pk=responded_to_id, deal_room=deal_room,
                )
            except NegotiationOffer.DoesNotExist:
                raise serializers.ValidationError({
                    "responded_to": (
                        "Offer uliyochagua haipo kwenye Deal Room hii."
                    )
                })

            if offer.offered_by_id == request.user.id:
                raise serializers.ValidationError({
                    "responded_to": "Huwezi kujibu offer yako mwenyewe."
                })

            if offer.status in [
                NegotiationOffer.Status.ACCEPTED,
                NegotiationOffer.Status.REJECTED,
                NegotiationOffer.Status.CANCELLED,
            ]:
                raise serializers.ValidationError({
                    "responded_to": "Offer hii haiwezi kujibiwa tena."
                })

        return attrs


class DealRoomListSerializer(serializers.ModelSerializer):
    listing_title = serializers.CharField(
        source="listing.title", read_only=True,
    )
    listing_price = serializers.DecimalField(
        source="listing.price",
        max_digits=15, decimal_places=2, read_only=True,
    )
    buyer_name = serializers.CharField(source="buyer.name", read_only=True)
    seller_name = serializers.CharField(source="seller.name", read_only=True)
    latest_offer = serializers.SerializerMethodField()

    class Meta:
        model = DealRoom
        fields = [
            "id", "listing", "listing_title", "listing_price",
            "buyer", "buyer_name", "seller", "seller_name",
            "status", "agreed_price", "agreed_at", "latest_offer",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_latest_offer(self, obj):
        offers = list(obj.offers.all())
        if not offers:
            return None
        offers.sort(key=lambda o: o.created_at, reverse=True)
        return NegotiationOfferSerializer(
            offers[0], context={**self.context, "deal_room": obj},
        ).data


class DealRoomDetailSerializer(serializers.ModelSerializer):
    listing = DealListingSerializer(read_only=True)
    buyer = DealUserSerializer(read_only=True)
    seller = DealUserSerializer(read_only=True)
    offers = NegotiationOfferSerializer(many=True, read_only=True)
    offer_count = serializers.SerializerMethodField()
    latest_offer = serializers.SerializerMethodField()

    class Meta:
        model = DealRoom
        fields = [
            "id", "listing", "buyer", "seller",
            "status", "agreed_price", "agreed_at",
            "offers", "offer_count", "latest_offer",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_offer_count(self, obj):
        return len(obj.offers.all())

    def get_latest_offer(self, obj):
        offers = list(obj.offers.all())
        if not offers:
            return None
        offers.sort(key=lambda o: o.created_at, reverse=True)
        return NegotiationOfferSerializer(
            offers[0], context={**self.context, "deal_room": obj},
        ).data


class DealRoomCreateSerializer(serializers.Serializer):
    listing_id = serializers.IntegerField(required=True)

    def validate_listing_id(self, value):
        try:
            listing = (
                Listing.objects
                .select_related("seller", "category")
                .get(pk=value)
            )
        except Listing.DoesNotExist:
            raise serializers.ValidationError("Tangazo halijapatikana.")

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
            listing=listing, buyer=request.user,
        ).first()

        if existing:
            raise serializers.ValidationError({
                "listing_id": (
                    f"Deal Room tayari ipo kwa tangazo hili. "
                    f"Deal Room ID: {existing.id}"
                )
            })

        return value

    def create(self, validated_data):
        request = self.context["request"]
        listing = Listing.objects.select_related("seller").get(
            pk=validated_data["listing_id"],
        )
        return DealRoom.objects.create(
            listing=listing,
            seller=listing.seller,
            buyer=request.user,
            status=DealRoom.Status.OPEN,
        )


class DealRoomCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=True, max_length=500,
    )

    def validate_reason(self, value):
        return value.strip()


class DealRoomAcceptOfferSerializer(serializers.Serializer):
    offer_id = serializers.IntegerField(required=True)

    def validate_offer_id(self, value):
        deal_room = self.context.get("deal_room")
        if not deal_room:
            raise serializers.ValidationError("Deal Room haijapatikana.")

        try:
            offer = NegotiationOffer.objects.get(
                pk=value, deal_room=deal_room,
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

        if request.user.id not in [deal_room.buyer_id, deal_room.seller_id]:
            raise serializers.ValidationError(
                "Huruhusiwi kukubali offer kwenye Deal Room hii."
            )

        if offer.offered_by_id == request.user.id:
            raise serializers.ValidationError(
                "Huwezi kukubali offer yako mwenyewe."
            )

        if offer.status != NegotiationOffer.Status.PENDING:
            raise serializers.ValidationError(
                "Offer hii haiwezi kukubaliwa kwa sababu hali yake "
                "si PENDING."
            )

        if deal_room.status not in [
            DealRoom.Status.OPEN,
            DealRoom.Status.NEGOTIATING,
        ]:
            raise serializers.ValidationError(
                "Deal Room hii haiwezi kukubali offer."
            )

        return value