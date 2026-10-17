"""Admin-specific deal serializers."""
from rest_framework import serializers

from apps.accounts.models import User
from apps.listings.models import Listing

from .models import DealRoom, NegotiationOffer




class UserMiniSerializer(serializers.ModelSerializer):
    """Compact user shape for nested buyer/seller in admin responses."""
    class Meta:
        model = User
        fields = ["id", "name", "email", "phone"]
        read_only_fields = fields


class ListingMiniSerializer(serializers.ModelSerializer):
    """Compact listing shape for nested listing in admin responses."""
    category_name = serializers.SerializerMethodField()
    category_slug = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "price", "location", "status",
            "category_name", "category_slug",
        ]
        read_only_fields = fields

    def get_category_name(self, obj):
        try:
            return obj.category.name if obj.category else ""
        except Exception:
            return ""

    def get_category_slug(self, obj):
        try:
            return obj.category.slug if obj.category else ""
        except Exception:
            return ""


class AdminOfferSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()
    at = serializers.DateTimeField(source="created_at", read_only=True)
    offerAmount = serializers.SerializerMethodField()

    class Meta:
        model = NegotiationOffer
        fields = ["id", "sender", "text", "at", "amount", "offerAmount", "status"]

    def get_sender(self, obj):
        room = self.context.get("deal_room") or obj.deal_room
        if obj.offered_by_id == room.buyer_id:
            return "buyer"
        if obj.offered_by_id == room.seller_id:
            return "seller"
        return "admin"

    def get_text(self, obj):
        return obj.message or ""

    def get_offerAmount(self, obj):
        return float(obj.amount)


class AdminDealRoomSerializer(serializers.ModelSerializer):
    # ── Nested objects (frontend reads these) ──
    buyer = UserMiniSerializer(read_only=True)
    seller = UserMiniSerializer(read_only=True)
    listing = ListingMiniSerializer(read_only=True)

    # ── Flat snake_case aliases (some normalizers prefer these) ──
    buyer_name = serializers.CharField(source="buyer.name", read_only=True)
    seller_name = serializers.CharField(source="seller.name", read_only=True)
    listing_title = serializers.CharField(source="listing.title", read_only=True)
    asking_price = serializers.DecimalField(
        source="listing.price", max_digits=15, decimal_places=2, read_only=True,
    )
    agreed_price = serializers.DecimalField(
        max_digits=15, decimal_places=2, read_only=True, allow_null=True,
    )
    current_offer = serializers.SerializerMethodField()

    buyerId = serializers.IntegerField(source="buyer.id", read_only=True)
    sellerId = serializers.IntegerField(source="seller.id", read_only=True)
    listingId = serializers.IntegerField(source="listing.id", read_only=True)
    listingTitle = serializers.CharField(source="listing.title", read_only=True)
    buyerName = serializers.CharField(source="buyer.name", read_only=True)
    sellerName = serializers.CharField(source="seller.name", read_only=True)
    askingPrice = serializers.DecimalField(
        source="listing.price", max_digits=15, decimal_places=2, read_only=True,
    )
    category = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    currentOffer = serializers.SerializerMethodField()
    messages = serializers.SerializerMethodField()
    reservationFee = serializers.SerializerMethodField()
    reservationHours = serializers.SerializerMethodField()
    reservationMethod = serializers.SerializerMethodField()
    reservationExpiresAt = serializers.SerializerMethodField()
    paymentProof = serializers.SerializerMethodField()

    class Meta:
        model = DealRoom
        fields = [
            "id", "status", "created_at", "updated_at",
            # Nested objects
            "buyer", "seller", "listing",
            # Flat camelCase aliases
            "buyerId", "sellerId", "listingId",
            "listingTitle", "buyerName", "sellerName", "askingPrice",
            # Flat snake_case aliases
            "buyer_name", "seller_name", "listing_title",
            "asking_price", "agreed_price", "current_offer",
            # Computed
            "category", "location",
            "currentOffer", "messages",
            "reservationFee", "reservationHours",
            "reservationMethod", "reservationExpiresAt",
            "paymentProof",
        ]

    def get_current_offer(self, obj):
        try:
            latest = obj.offers.order_by("-created_at").first()
            return float(latest.amount) if latest else 0
        except Exception:
            return 0

    def _txn(self, obj):
        return getattr(obj, "transaction", None)

    def _reservation(self, obj):
        txn = self._txn(obj)
        return getattr(txn, "reservation", None) if txn else None

    def get_category(self, obj):
        try:
            if obj.listing and obj.listing.category:
                return obj.listing.category.name
        except Exception:
            pass
        return ""

    def get_location(self, obj):
        try:
            return obj.listing.location if obj.listing else ""
        except Exception:
            return ""

    def get_currentOffer(self, obj):
        try:
            latest = obj.offers.order_by("-created_at").first()
        except Exception:
            latest = None
        if not latest:
            try:
                return float(obj.agreed_price) if obj.agreed_price else 0
            except Exception:
                return 0
        return float(latest.amount)

    def get_messages(self, obj):
        try:
            qs = obj.offers.order_by("created_at")
        except Exception:
            return []
        out = []
        for o in qs:
            try:
                room = o.deal_room
                if o.offered_by_id == room.buyer_id:
                    sender = "buyer"
                elif o.offered_by_id == room.seller_id:
                    sender = "seller"
                else:
                    sender = "admin"
            except Exception:
                sender = "unknown"
            out.append({
                "id": o.id, "sender": sender, "text": o.message or "",
                "amount": float(o.amount), "status": o.status, "at": o.created_at,
            })
        return out

    def get_reservationFee(self, obj):
        r = self._reservation(obj)
        try:
            return float(r.deposit_amount) if r else None
        except Exception:
            return None

    def get_reservationHours(self, obj):
        r = self._reservation(obj)
        return getattr(r, "duration_hours", None) if r else None

    def get_reservationMethod(self, obj):
        r = self._reservation(obj)
        return getattr(r, "payment_method", None) if r else None

    def get_reservationExpiresAt(self, obj):
        r = self._reservation(obj)
        return getattr(r, "expires_at", None) if r else None

    def get_paymentProof(self, obj):
        txn = self._txn(obj)
        if not txn:
            return None
        proof = getattr(txn, "final_payment_proof", None)
        if not proof:
            return None
        try:
            url = proof.url
        except Exception:
            url = None
        return {
            "method": "Bank/Card",
            "reference": txn.final_payment_reference or "",
            "submittedAt": txn.final_payment_uploaded_at,
            "url": url,
        }