# apps/deals/serializers_admin.py
from rest_framework import serializers

from .models import DealRoom, NegotiationOffer


class AdminOfferSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    text = serializers.SerializerMethodField()
    at = serializers.DateTimeField(source="created_at", read_only=True)

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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["offerAmount"] = float(instance.amount)
        return data


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
    reservationMethod = serializers.CharField(
        source="transaction.reservation.payment_method",
        read_only=True, allow_null=True,
    )
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

    def get_currentOffer(self, obj):
        latest = obj.offers.order_by("-created_at").first()
        if not latest:
            return float(obj.agreed_price or obj.listing.price)
        return float(latest.amount)

    def get_messages(self, obj):
        return [
            AdminOfferSerializer(o, context={"deal_room": obj}).data
            for o in obj.offers.order_by("created_at")
        ]

    def get_reservationFee(self, obj):
        try:
            r = obj.transaction.reservation
            return float(r.deposit_amount)
        except Exception:
            return None

    def get_reservationHours(self, obj):
        try:
            return obj.transaction.reservation.duration_hours
        except Exception:
            return None

    def get_reservationExpiresAt(self, obj):
        try:
            return obj.transaction.reservation.expires_at
        except Exception:
            return None

    def get_paymentProof(self, obj):
        try:
            t = obj.transaction
            if t.final_payment_proof:
                return {
                    "method": "Bank/Card",
                    "reference": t.final_payment_reference or "",
                    "submittedAt": t.final_payment_uploaded_at,
                    "url": t.final_payment_proof.url,
                }
        except Exception:
            pass
        return None

    def get_disputeNote(self, obj):
        try:
            return obj.transaction.cancellation_reason or ""
        except Exception:
            return ""
