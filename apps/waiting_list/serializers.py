from rest_framework import serializers

from apps.listings.models import Listing

from .models import WaitingListEntry


class WaitingListListingSerializer(serializers.ModelSerializer):
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
            "created_at",
        ]
        read_only_fields = fields


class WaitingListBuyerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)


class WaitingListEntrySerializer(serializers.ModelSerializer):
    listing = WaitingListListingSerializer(read_only=True)
    buyer = WaitingListBuyerSerializer(read_only=True)

    class Meta:
        model = WaitingListEntry
        fields = [
            "id",
            "listing",
            "buyer",
            "status",
            "position",
            "notified_at",
            "joined_at",
            "updated_at",
        ]
        read_only_fields = fields


class WaitingListCreateSerializer(serializers.Serializer):
    listing = serializers.PrimaryKeyRelatedField(
        queryset=Listing.objects.all(),
        write_only=True,
    )

    def validate_listing(self, listing):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Lazima uwe umeingia kwenye akaunti."
            )

        user = request.user

        if not user.is_active:
            raise serializers.ValidationError(
                "Akaunti yako haijawezeshwa."
            )

        if not user.is_verified:
            raise serializers.ValidationError(
                "Akaunti yako lazima iwe imethibitishwa."
            )

        if listing.seller_id == user.id:
            raise serializers.ValidationError(
                "Huwezi kujiunga kwenye waiting list ya tangazo lako."
            )

        if listing.status != Listing.Status.RESERVED:
            raise serializers.ValidationError(
                "Waiting list inapatikana kwa matangazo "
                "yaliyo kwenye hali ya RESERVED pekee."
            )

        return listing

    def validate(self, attrs):
        request = self.context.get("request")
        listing = attrs["listing"]

        if WaitingListEntry.objects.filter(
            listing=listing,
            buyer=request.user,
        ).exists():
            raise serializers.ValidationError(
                {
                    "listing": (
                        "Tayari umejiunga kwenye waiting list "
                        "ya tangazo hili."
                    )
                }
            )

        return attrs


class WaitingListCancelSerializer(serializers.Serializer):
    pass