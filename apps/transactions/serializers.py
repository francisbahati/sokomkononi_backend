from django.db import transaction as db_transaction
from rest_framework import serializers

from apps.deals.models import DealRoom, NegotiationOffer

from .models import InspectionPeriod, Reservation, Transaction


# ============================================================================
# BASIC NESTED SERIALIZERS
# ============================================================================

class TransactionUserSerializer(serializers.Serializer):
    """
    Small public representation of a transaction participant.
    """

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)


class TransactionListingSerializer(serializers.Serializer):
    """
    Basic listing information shown inside a transaction.
    """

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    price = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )
    status = serializers.CharField(read_only=True)
    location = serializers.CharField(read_only=True)


# ============================================================================
# RESERVATION SERIALIZER
# ============================================================================

class ReservationSerializer(serializers.ModelSerializer):
    """
    Read-only representation of a reservation.

    Reservation payment/status/timing are controlled by the transaction
    and reservation services. Clients must not modify these directly.
    """

    class Meta:
        model = Reservation
        fields = [
            "id",
            "transaction",
            "deposit_amount",
            "payment_status",
            "payment_reference",
            "paid_at",
            "duration_hours",
            "starts_at",
            "expires_at",
            "status",
            "refund_reference",
            "refunded_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ============================================================================
# INSPECTION PERIOD SERIALIZER
# ============================================================================

class InspectionPeriodSerializer(serializers.ModelSerializer):
    """
    Read-only representation of the inspection period.

    Inspection timing is controlled by the transaction workflow.
    """

    class Meta:
        model = InspectionPeriod
        fields = [
            "id",
            "transaction",
            "duration_hours",
            "starts_at",
            "expires_at",
            "status",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ============================================================================
# TRANSACTION LIST SERIALIZER
# ============================================================================

class TransactionListSerializer(serializers.ModelSerializer):
    """
    Lightweight transaction representation for dashboards and lists.
    """

    listing = TransactionListingSerializer(read_only=True)
    buyer = TransactionUserSerializer(read_only=True)
    seller = TransactionUserSerializer(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "deal_room",
            "listing",
            "buyer",
            "seller",
            "agreed_price",
            "status",
            "buyer_decision",
            "seller_confirmed_payment",
            "completed_at",
            "cancelled_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


# ============================================================================
# TRANSACTION DETAIL SERIALIZER
# ============================================================================

class TransactionDetailSerializer(serializers.ModelSerializer):
    """
    Full transaction representation.

    Includes reservation and inspection information when available.
    """

    listing = TransactionListingSerializer(read_only=True)
    buyer = TransactionUserSerializer(read_only=True)
    seller = TransactionUserSerializer(read_only=True)

    reservation = ReservationSerializer(read_only=True)
    inspection_period = InspectionPeriodSerializer(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "deal_room",
            "listing",
            "buyer",
            "seller",
            "agreed_price",
            "status",
            "buyer_decision",
            "buyer_decision_note",
            "buyer_decision_at",
            "final_payment_proof",
            "final_payment_reference",
            "final_payment_uploaded_at",
            "seller_confirmed_payment",
            "seller_confirmed_at",
            "completed_at",
            "cancelled_at",
            "cancellation_reason",
            "reservation",
            "inspection_period",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "deal_room",
            "listing",
            "buyer",
            "seller",
            "agreed_price",
            "status",
            "buyer_decision",
            "buyer_decision_note",
            "buyer_decision_at",
            "final_payment_proof",
            "final_payment_reference",
            "final_payment_uploaded_at",
            "seller_confirmed_payment",
            "seller_confirmed_at",
            "completed_at",
            "cancelled_at",
            "cancellation_reason",
            "reservation",
            "inspection_period",
            "created_at",
            "updated_at",
        ]


# ============================================================================
# CREATE TRANSACTION SERIALIZER
# ============================================================================

class TransactionCreateSerializer(serializers.Serializer):
    """
    Creates a transaction from an AGREED Deal Room.

    The client supplies only:
        deal_room

    The following are NEVER trusted from the client:
        - buyer
        - seller
        - listing
        - agreed_price
        - status

    They are derived directly from the Deal Room.
    """

    deal_room = serializers.PrimaryKeyRelatedField(
        queryset=DealRoom.objects.select_related(
            "listing",
            "buyer",
            "seller",
        ),
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

        if Transaction.objects.filter(
            deal_room=deal_room
        ).exists():
            raise serializers.ValidationError(
                "Transaction tayari imeundwa kwa Deal Room hii."
            )

        return deal_room

    def create(self, validated_data):
        deal_room = validated_data["deal_room"]

        with db_transaction.atomic():
            transaction = Transaction.objects.create(
                deal_room=deal_room,
                listing=deal_room.listing,
                buyer=deal_room.buyer,
                seller=deal_room.seller,
                agreed_price=deal_room.agreed_price,
                status=Transaction.Status.PENDING,
            )

        return transaction


# ============================================================================
# BUYER DECISION SERIALIZER
# ============================================================================

class BuyerDecisionSerializer(serializers.Serializer):
    """
    Buyer submits a decision after inspection.
    """

    buyer_decision = serializers.ChoiceField(
        choices=Transaction.BuyerDecision.choices
    )

    buyer_decision_note = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        request = self.context.get("request")
        transaction = self.context.get("transaction")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Lazima uwe umeingia kwenye akaunti."
            )

        if transaction is None:
            raise serializers.ValidationError(
                "Transaction haijapatikana."
            )

        if request.user.id != transaction.buyer_id:
            raise serializers.ValidationError(
                "Uamuzi huu unaweza kufanywa na mnunuzi pekee."
            )

        if transaction.status != Transaction.Status.INSPECTION:
            raise serializers.ValidationError(
                "Uamuzi wa mnunuzi unaweza kufanywa wakati wa inspection pekee."
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


# ============================================================================
# FINAL PAYMENT PROOF SERIALIZER
# ============================================================================

class FinalPaymentProofSerializer(serializers.Serializer):
    """
    Buyer uploads proof of the final payment made directly to the seller.
    """

    final_payment_proof = serializers.FileField(
        required=True
    )

    final_payment_reference = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )

    def validate(self, attrs):
        request = self.context.get("request")
        transaction = self.context.get("transaction")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Lazima uwe umeingia kwenye akaunti."
            )

        if transaction is None:
            raise serializers.ValidationError(
                "Transaction haijapatikana."
            )

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
            max_size = 10 * 1024 * 1024

            if proof.size > max_size:
                raise serializers.ValidationError(
                    "Faili haliwezi kuzidi 10MB."
                )

        attrs["final_payment_reference"] = (
            attrs.get("final_payment_reference", "").strip()
        )

        return attrs


# ============================================================================
# SELLER PAYMENT CONFIRMATION SERIALIZER
# ============================================================================

class SellerConfirmPaymentSerializer(serializers.Serializer):
    """
    Seller confirms that the final payment was received.
    """

    confirmation_note = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        request = self.context.get("request")
        transaction = self.context.get("transaction")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Lazima uwe umeingia kwenye akaunti."
            )

        if transaction is None:
            raise serializers.ValidationError(
                "Transaction haijapatikana."
            )

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


# ============================================================================
# CANCEL TRANSACTION SERIALIZER
# ============================================================================

class TransactionCancelSerializer(serializers.Serializer):
    """
    Allows an eligible participant to request transaction cancellation.
    """

    cancellation_reason = serializers.CharField(
        required=True,
    )

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


# ============================================================================
# TRANSACTION DASHBOARD SERIALIZER
# ============================================================================

class MyTransactionSerializer(serializers.ModelSerializer):
    """
    Dashboard-friendly transaction serializer.

    Useful for:
        /my-transactions/
    """

    listing_title = serializers.CharField(
        source="listing.title",
        read_only=True,
    )

    listing_status = serializers.CharField(
        source="listing.status",
        read_only=True,
    )

    other_party_name = serializers.SerializerMethodField()

    reservation_status = serializers.SerializerMethodField()
    reservation_expires_at = serializers.SerializerMethodField()

    inspection_status = serializers.SerializerMethodField()
    inspection_expires_at = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "deal_room",
            "listing",
            "listing_title",
            "listing_status",
            "agreed_price",
            "status",
            "buyer_decision",
            "other_party_name",
            "reservation_status",
            "reservation_expires_at",
            "inspection_status",
            "inspection_expires_at",
            "created_at",
            "updated_at",
            "completed_at",
            "cancelled_at",
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
        reservation = getattr(obj, "reservation", None)

        if reservation is None:
            return None

        return reservation.status

    def get_reservation_expires_at(self, obj):
        reservation = getattr(obj, "reservation", None)

        if reservation is None:
            return None

        return reservation.expires_at

    def get_inspection_status(self, obj):
        inspection = getattr(obj, "inspection_period", None)

        if inspection is None:
            return None

        return inspection.status

    def get_inspection_expires_at(self, obj):
        inspection = getattr(obj, "inspection_period", None)

        if inspection is None:
            return None

        return inspection.expires_at