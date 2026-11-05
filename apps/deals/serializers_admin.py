# apps/deals/serializers_admin.py
"""Admin-specific deal serializers."""
from rest_framework import serializers

from apps.accounts.models import User
from apps.listings.models import Listing

from .models import DealMessage, DealRoom, NegotiationOffer


# ============================================================
# MINI SERIALIZERS (nested)
# ============================================================
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


# ============================================================
# OFFERS (admin shape)
# ============================================================
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


# ============================================================
# MESSAGES (admin shape — inaonyesha kind + is_hidden)
# ============================================================
class AdminDealMessageSerializer(serializers.ModelSerializer):
    """
    Ujumbe wa Deal Room kwa admin.
    Admin anaona kila kitu — pamoja na ujumbe uliofichwa.
    """
    # ── FIX: `sender_id` haina attribute moja kwa moja kwenye model,
    #         kwa hiyo tunatumia source="sender.id" ──
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)
    sender_name = serializers.SerializerMethodField()
    kind = serializers.CharField(read_only=True)

    class Meta:
        model = DealMessage
        fields = [
            "id", "sender_id", "sender_name", "text",
            "kind", "is_hidden", "created_at",
        ]
        read_only_fields = fields

    def get_sender_name(self, obj):
        return getattr(obj.sender, "name", "")


# ============================================================
# DEAL ROOM (admin shape)
# ============================================================
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

    # ── MPYA: admin moderation fields ──
    admin_locked = serializers.BooleanField(read_only=True)
    locked_reason = serializers.CharField(read_only=True)
    locked_at = serializers.DateTimeField(read_only=True)
    locked_by = serializers.SerializerMethodField()
    locked_by_name = serializers.SerializerMethodField()
    cancelled_by_admin = serializers.BooleanField(read_only=True)

    # ── CamelCase aliases kwa frontend ──
    adminLocked = serializers.BooleanField(source="admin_locked", read_only=True)
    lockedReason = serializers.CharField(source="locked_reason", read_only=True)
    lockedAt = serializers.DateTimeField(source="locked_at", read_only=True)
    lockedByName = serializers.SerializerMethodField()
    cancelledByAdmin = serializers.BooleanField(
        source="cancelled_by_admin", read_only=True,
    )

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
            # ── MPYA: admin moderation ──
            "admin_locked", "locked_reason", "locked_at",
            "locked_by", "locked_by_name", "cancelled_by_admin",
            "adminLocked", "lockedReason", "lockedAt",
            "lockedByName", "cancelledByAdmin",
        ]

    # ── Existing helpers ──
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
        """
        Admin anaona ujumbe WOTE — pamoja na wa USER, ADMIN, na
        uliofichwa (is_hidden). Ujumbe wa admin una `sender = "admin"`.
        """
        try:
            qs = obj.messages.select_related("sender").order_by("created_at")
        except Exception:
            return []
        out = []
        for m in qs:
            try:
                sender = "admin" if m.kind == DealMessage.Kind.ADMIN else (
                    "buyer" if m.sender_id == obj.buyer_id else
                    "seller" if m.sender_id == obj.seller_id else
                    "unknown"
                )
            except Exception:
                sender = "unknown"
            out.append({
                "id": m.id,
                "sender": sender,
                "senderId": m.sender_id,
                "senderName": getattr(m.sender, "name", ""),
                "text": m.text or "",
                "kind": m.kind,
                "isHidden": m.is_hidden,
                "at": m.created_at,
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

    # ── MPYA: admin moderation helpers ──
    def get_locked_by(self, obj):
        return obj.locked_by_id

    def get_locked_by_name(self, obj):
        if not obj.locked_by:
            return ""
        return getattr(obj.locked_by, "name", "")

    def get_lockedByName(self, obj):
        return self.get_locked_by_name(obj)


# ============================================================
# ADMIN ACTION SERIALIZERS
# ============================================================
class AdminDealMessageCreateSerializer(serializers.Serializer):
    """
    Admin anatuma ujumbe kwenye Deal Room kama msimamizi.
    Ujumbe huu una `kind = ADMIN` na unaonekana kwa pande zote mbili.
    """
    text = serializers.CharField(
        required=True, allow_blank=False, trim_whitespace=True,
        max_length=2000,
    )

    def validate_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Ujumbe hauwezi kuwa tupu.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        deal_room = self.context.get("deal_room")

        if not deal_room:
            raise serializers.ValidationError("Deal Room haijapatikana.")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Ni lazima uwe umeingia kwenye akaunti."
            )
        if not request.user.is_staff:
            raise serializers.ValidationError(
                "Ni admin pekee anayeweza kutuma ujumbe wa admin."
            )
        if deal_room.status == DealRoom.Status.CANCELLED:
            raise serializers.ValidationError(
                "Deal Room hii imeghairiwa — haiwezi kupokea ujumbe mpya."
            )
        return attrs


class AdminDealLockSerializer(serializers.Serializer):
    """Admin anasimamisha room. Sababu ni lazima."""
    reason = serializers.CharField(
        required=True, allow_blank=False, trim_whitespace=True,
        max_length=1000,
    )

    def validate_reason(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "Sababu ya kusimamisha ni lazima."
            )
        return value

    def validate(self, attrs):
        deal_room = self.context.get("deal_room")
        if not deal_room:
            raise serializers.ValidationError("Deal Room haijapatikana.")
        if deal_room.admin_locked:
            raise serializers.ValidationError(
                "Deal Room hii tayari imesimamishwa."
            )
        if deal_room.status == DealRoom.Status.CANCELLED:
            raise serializers.ValidationError(
                "Deal Room iliyoghairiwa haiwezi kusimamishwa."
            )
        return attrs


class AdminDealUnlockSerializer(serializers.Serializer):
    """Admin anafungua room iliyosimamishwa. Sababu ni hiari."""
    reason = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=True,
        max_length=1000,
    )

    def validate_reason(self, value):
        return (value or "").strip()

    def validate(self, attrs):
        deal_room = self.context.get("deal_room")
        if not deal_room:
            raise serializers.ValidationError("Deal Room haijapatikana.")
        if not deal_room.admin_locked:
            raise serializers.ValidationError(
                "Deal Room hii haijasimamishwa."
            )
        return attrs


class AdminDealCancelSerializer(serializers.Serializer):
    """
    Admin anaghairi Deal Room. Sababu ni lazima na inaingia kwenye audit.
    Deal iliyoghairiwa na admin haiwezi kufufuliwa na mtumiaji.
    """
    reason = serializers.CharField(
        required=True, allow_blank=False, trim_whitespace=True,
        max_length=1000,
    )

    def validate_reason(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "Sababu ya kughairi ni lazima."
            )
        return value

    def validate(self, attrs):
        deal_room = self.context.get("deal_room")
        if not deal_room:
            raise serializers.ValidationError("Deal Room haijapatikana.")
        if deal_room.status == DealRoom.Status.CANCELLED:
            raise serializers.ValidationError(
                "Deal Room hii tayari imeghairiwa."
            )
        if deal_room.status == DealRoom.Status.COMPLETED:
            raise serializers.ValidationError(
                "Deal Room iliyokamilika haiwezi kughairiwa."
            )
        return attrs