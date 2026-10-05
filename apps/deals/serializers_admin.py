# apps/deals/serializers_admin.py
from rest_framework import serializers

from .models import DealRoom, NegotiationOffer


class AdminOfferSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()
    at = serializers.DateTimeField(source="created_at", read_only=True)
    offerAmount = serializers.SerializerMethodField()

    class Meta:
        model = NegotiationOffer
        fields = [
            "id", "sender", "text", "at",
            "amount", "offerAmount", "status",
        ]

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
    listingTitle = serializers.CharField(source="listing.title", read_only=True)
    buyerName = serializers.CharField(source="buyer.name", read_only=True)
    sellerName = serializers.CharField(source="seller.name", read_only=True)
    askingPrice = serializers.DecimalField(
        source="listing.price", max_digits=15, decimal_places=2,
        read_only=True,
    )
    currentOffer = serializers.SerializerMethodField()
    messages = serializers.SerializerMethodField()
    reservationFee = serializers.SerializerMethodField()
    reservationHours = serializers.SerializerMethodField()
    reservationMethod = serializers.SerializerMethodField()
    reservationExpiresAt = serializers.SerializerMethodField()
    paymentProof = serializers.SerializerMethodField()
    disputeNote = serializers.SerializerMethodField()

    class Meta:
        model = DealRoom
        fields = [
            "id", "status", "listingTitle", "buyerName", "sellerName",
            "askingPrice", "currentOffer", "messages",
            "reservationFee", "reservationHours", "reservationMethod",
            "reservationExpiresAt", "paymentProof", "disputeNote",
            "created_at", "updated_at",
        ]

    # ── Helpers ────────────────────────────────────────────
    def _txn(self, obj):
        return getattr(obj, "transaction", None)

    def _reservation(self, obj):
        txn = self._txn(obj)
        return getattr(txn, "reservation", None) if txn else None

    # ── Current offer ──────────────────────────────────────
    def get_currentOffer(self, obj):
        latest = obj.offers.order_by("-created_at").first()
        if not latest:
            return float(obj.agreed_price) if obj.agreed_price else 0
        return float(latest.amount)

    # ── Messages (offers as bubbles) ───────────────────────
    def get_messages(self, obj):
        return [
            AdminOfferSerializer(o, context={"deal_room": obj}).data
            for o in obj.offers.order_by("created_at")
        ]

    # ── Reservation fields ─────────────────────────────────
    def get_reservationFee(self, obj):
        r = self._reservation(obj)
        return float(r.deposit_amount) if r else None

    def get_reservationHours(self, obj):
        r = self._reservation(obj)
        return r.duration_hours if r else None

    def get_reservationMethod(self, obj):
        r = self._reservation(obj)
        return getattr(r, "payment_method", None) if r else None

    def get_reservationExpiresAt(self, obj):
        r = self._reservation(obj)
        return r.expires_at if r else None

    # ── Payment proof ──────────────────────────────────────
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

    # ── Dispute note ───────────────────────────────────────
    def get_disputeNote(self, obj):
        txn = self._txn(obj)
        if not txn:
            return ""
        return txn.cancellation_reason or ""