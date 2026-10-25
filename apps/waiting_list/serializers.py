# apps/waiting_list/serializers.py

from rest_framework import serializers
from apps.listings.models import Listing
from .models import WaitingListEntry


class WaitingListListingSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "price", "location", "status", 
            "category", "is_featured", "is_boosted", "created_at"
        ]
        read_only_fields = fields

    def get_category(self, obj):
        c = getattr(obj, "category", None)
        return {"id": c.id, "name": c.name, "slug": c.slug} if c else None


class WaitingListBuyerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)


class WaitingListEntrySerializer(serializers.ModelSerializer):
    listing = WaitingListListingSerializer(read_only=True)
    buyer = WaitingListBuyerSerializer(read_only=True)
    
    reservation_expires_at = serializers.SerializerMethodField()

    class Meta:
        model = WaitingListEntry
        fields = [
            "id", "listing", "buyer", "status", "position", 
            "notified_at", "respond_by", "joined_at", "updated_at",
            "reservation_expires_at" 
        ]
        read_only_fields = fields

    def get_reservation_expires_at(self, obj):
        """
        Rudisha muda ambao reservation ya sasa inaisha.
        Hii inatumika kwenye frontend kuonyesha countdown.
        """
        from apps.transactions.models import Reservation
        
        # Tafuta reservation active ya listing hii
        reservation = Reservation.objects.filter(
            transaction__listing_id=obj.listing_id,
            status=Reservation.Status.ACTIVE,
        ).order_by("-created_at").first()
        
        if reservation and getattr(reservation, "expires_at", None):
            return reservation.expires_at.isoformat()
        return None


class WaitingListCreateSerializer(serializers.Serializer):
    listing = serializers.PrimaryKeyRelatedField(
        queryset=Listing.objects.all(), 
        write_only=True
    )

    def validate_listing(self, listing):
        req = self.context.get("request")
        if not req or not req.user.is_authenticated:
            raise serializers.ValidationError("Login required.")
        
        u = req.user
        if not u.is_active:
            raise serializers.ValidationError("Akaunti haijawezeshwa.")
        if not u.is_verified:
            raise serializers.ValidationError("Akaunti lazima iwe imethibitishwa.")
        if listing.seller_id == u.id:
            raise serializers.ValidationError("Huwezi kujiunga kwenye tangazo lako.")
        if listing.status != Listing.Status.RESERVED:
            raise serializers.ValidationError("Tangazo lazima liwe RESERVED.")
        
        return listing

    def validate(self, a):
        req = self.context.get("request")
        l = a["listing"]
        
        if WaitingListEntry.objects.filter(
            listing=l, 
            buyer=req.user,
            status__in=[
                WaitingListEntry.Status.WAITING, 
                WaitingListEntry.Status.NOTIFIED
            ]
        ).exists():
            raise serializers.ValidationError({"listing": "Tayari umejiunga."})
        
        return a


class WaitingListCancelSerializer(serializers.Serializer):
    pass