from rest_framework import serializers

from apps.deals.models import DealRoom

from .models import InspectionPeriod, Reservation, Transaction


class TransactionUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True, allow_null=True)


class TransactionListingSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    price = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)
    location = serializers.CharField(read_only=True)


class ReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reservation
        fields = [
            "id", "transaction", "deposit_amount", "payment_status",
            "payment_reference", "paid_at", "duration_hours",
            "starts_at", "expires_at", "status",
            "refund_reference", "refunded_at",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class InspectionPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = InspectionPeriod
        fields = [
            "id", "transaction", "duration_hours",
            "starts_at", "expires_at", "status",
            "completed_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class TransactionListSerializer(serializers.ModelSerializer):
    listing = TransactionListingSerializer(read_only=True)
    buyer = TransactionUserSerializer(read_only=True)
    seller = TransactionUserSerializer(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id", "deal_room", "listing", "buyer", "seller",
            "agreed_price", "status", "buyer_decision",
            "seller_confirmed_payment", "completed_at", "cancelled_at",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class TransactionDetailSerializer(serializers.ModelSerializer):
    listing = TransactionListingSerializer(read_only=True)
    buyer = TransactionUserSerializer(read_only=True)
    seller = TransactionUserSerializer(read_only=True)
    reservation = ReservationSerializer(read_only=True)
    inspection_period = InspectionPeriodSerializer(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id", "deal_room", "listing", "buyer", "seller",
            "agreed_price", "status", "buyer_decision",
            "buyer_decision_note", "buyer_decision_at",
            "final_payment_proof", "final_payment_reference",
            "final_payment_uploaded_at", "seller_confirmed_payment",
            "seller_confirmed_at", "completed_at", "cancelled_at",
            "cancellation_reason", "dispute_resolved_by",
            "dispute_resolution_note", "reservation", "inspection_period",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class TransactionCreateSerializer(serializers.Serializer):
    deal_room = serializers.PrimaryKeyRelatedField(
        queryset=DealRoom.objects.all(),
    )

    def validate_deal_room(self, deal_room):
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Lazima uwe umeingia kwenye akaunti."
            )

        user = request.user
        if not user.is_active or not user.is_verified:
            raise serializers.ValidationError(
                "Akaunti yako lazima iwe active na imethibitishwa."
            )

        if user.id not in [deal_room.buyer_id, deal_room.seller_id]:
            raise serializers.ValidationError(
                "Huruhusiwi kuunda Transaction ya Deal Room hii."
            )

        if deal_room.status != DealRoom.Status.AGREED:
            raise serializers.ValidationError(
                "Transaction inaweza kuundwa tu baada ya Deal Room "
                "kukubaliana bei."
            )

        if deal_room.agreed_price is None:
            raise serializers.ValidationError(
                "Deal Room haina bei iliyokubaliwa."
            )

        if Transaction.objects.filter(deal_room=deal_room).exists():
            raise serializers.ValidationError(
                "Transaction tayari imeundwa kwa Deal Room hii."
            )

        return deal_room


class BuyerDecisionSerializer(serializers.Serializer):
    buyer_decision = serializers.ChoiceField(
        choices=Transaction.BuyerDecision.choices,
    )
    buyer_decision_note = serializers.CharField(
        required=False, allow_blank=True,
    )

    def validate(self, attrs):
        request = self.context.get("request")
        transaction = self.context.get("transaction")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Lazima uwe umeingia kwenye akaunti."
            )
        if transaction is None:
            raise serializers.ValidationError("Transaction haijapatikana.")
        if request.user.id != transaction.buyer_id:
            raise serializers.ValidationError(
                "Uamuzi huu unaweza kufanywa na mnunuzi pekee."
            )
        if transaction.status != Transaction.Status.INSPECTION:
            raise serializers.ValidationError(
                "Uamuzi wa mnunuzi unaweza kufanywa wakati wa "
                "inspection pekee."
            )

        decision = attrs["buyer_decision"]
        if decision == Transaction.BuyerDecision.PENDING:
            raise serializers.ValidationError(
                "Lazima uchague uamuzi halali."
            )

        note = attrs.get("buyer_decision_note", "").strip()
        if decision in [
            Transaction.BuyerDecision.NOT_AS_DESCRIBED,
            Transaction.BuyerDecision.REQUEST_NEGOTIATION,
            Transaction.BuyerDecision.CANCEL_TRANSACTION,
        ] and not note:
            raise serializers.ValidationError(
                "Tafadhali toa maelezo ya uamuzi wako."
            )

        attrs["buyer_decision_note"] = note
        return attrs


ALLOWED_PROOF_MIME = {
    "image/jpeg", "image/png", "image/webp",
    "application/pdf",
}


class FinalPaymentProofSerializer(serializers.Serializer):
    final_payment_proof = serializers.FileField(required=True)
    final_payment_reference = serializers.CharField(
        required=False, allow_blank=True, max_length=255,
    )

    def validate(self, attrs):
        request = self.context.get("request")
        transaction = self.context.get("transaction")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Lazima uwe umeingia kwenye akaunti."
            )
        if transaction is None:
            raise serializers.ValidationError("Transaction haijapatikana.")
        if request.user.id != transaction.buyer_id:
            raise serializers.ValidationError(
                "Ushahidi wa malipo unaweza kupakiwa na mnunuzi pekee."
            )
        if transaction.status != Transaction.Status.READY_FOR_FINAL_PAYMENT:
            raise serializers.ValidationError(
                "Transaction haijawa tayari kwa malipo ya mwisho."
            )

        proof = attrs.get("final_payment_proof")
        if proof:
            if proof.size > 10 * 1024 * 1024:
                raise serializers.ValidationError(
                    "Faili haliwezi kuzidi 10MB."
                )
            content_type = getattr(proof, "content_type", None)
            if content_type and content_type not in ALLOWED_PROOF_MIME:
                raise serializers.ValidationError(
                    "Aina ya faili hairuhusiwi. Tumia JPG, PNG, WEBP au PDF."
                )

        attrs["final_payment_reference"] = (
            attrs.get("final_payment_reference", "").strip()
        )
        return attrs


class SellerConfirmPaymentSerializer(serializers.Serializer):
    confirmation_note = serializers.CharField(
        required=False, allow_blank=True,
    )

    def validate(self, attrs):
        request = self.context.get("request")
        transaction = self.context.get("transaction")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Lazima uwe umeingia kwenye akaunti."
            )
        if transaction is None:
            raise serializers.ValidationError("Transaction haijapatikana.")
        if request.user.id != transaction.seller_id:
            raise serializers.ValidationError(
                "Uthibitisho wa malipo unaweza kufanywa na muuzaji pekee."
            )
        if transaction.status != Transaction.Status.READY_FOR_FINAL_PAYMENT:
            raise serializers.ValidationError(
                "Transaction haipo kwenye hatua ya malipo ya mwisho."
            )
        if not transaction.final_payment_proof:
            raise serializers.ValidationError(
                "Mnunuzi bado hajapakia ushahidi wa malipo ya mwisho."
            )
        if transaction.seller_confirmed_payment:
            raise serializers.ValidationError(
                "Malipo tayari yamethibitishwa."
            )

        attrs["confirmation_note"] = (
            attrs.get("confirmation_note", "").strip()
        )
        return attrs


class TransactionCancelSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(required=True)

    def validate_cancellation_reason(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError(
                "Sababu ya kughairi haiwezi kuwa tupu."
            )
        if len(value) < 5:
            raise serializers.ValidationError(
                "Tafadhali toa sababu yenye maelezo ya kutosha."
            )
        return value


class MyTransactionSerializer(serializers.ModelSerializer):
    listing_title = serializers.CharField(
        source="listing.title", read_only=True,
    )
    listing_status = serializers.CharField(
        source="listing.status", read_only=True,
    )
    other_party_name = serializers.SerializerMethodField()
    reservation_status = serializers.SerializerMethodField()
    reservation_expires_at = serializers.SerializerMethodField()
    inspection_status = serializers.SerializerMethodField()
    inspection_expires_at = serializers.SerializerMethodField()
    has_reservation = serializers.SerializerMethodField()
    has_inspection = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id", "deal_room", "listing", "listing_title", "listing_status",
            "agreed_price", "status", "buyer_decision", "other_party_name",
            "reservation_status", "reservation_expires_at",
            "inspection_status", "inspection_expires_at",
            "has_reservation", "has_inspection",
            "created_at", "updated_at", "completed_at", "cancelled_at",
        ]
        read_only_fields = fields

    def get_other_party_name(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        if request.user.id == obj.buyer_id:
            return obj.seller.name
        if request.user.id == obj.seller_id:
            return obj.buyer.name
        return None

    def get_reservation_status(self, obj):
        r = getattr(obj, "reservation", None)
        return r.status if r else None

    def get_reservation_expires_at(self, obj):
        r = getattr(obj, "reservation", None)
        return r.expires_at if r else None

    def get_inspection_status(self, obj):
        i = getattr(obj, "inspection_period", None)
        return i.status if i else None

    def get_inspection_expires_at(self, obj):
        i = getattr(obj, "inspection_period", None)
        return i.expires_at if i else None

    def get_has_reservation(self, obj):
        return hasattr(obj, "reservation")

    def get_has_inspection(self, obj):
        return hasattr(obj, "inspection_period")