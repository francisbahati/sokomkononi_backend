# apps/deals/serializers.py
import re
from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import User
from apps.listings.models import Listing

from .models import DealMessage, DealRoom, NegotiationOffer


# ============================================================
# PHONE / EMAIL DETECTION
# ============================================================
_PHONE_PATTERNS = [
    re.compile(r"\b0[4-9]\d{7,8}\b"),
    re.compile(r"\+255\d{7,9}\b"),
    re.compile(r"\b255\d{7,9}\b"),
    re.compile(r"\+254\d{7,9}\b"),
    re.compile(r"\b254\d{7,9}\b"),
    re.compile(r"\+256\d{7,9}\b"),
    re.compile(r"\b256\d{7,9}\b"),
    re.compile(r"\+\d{8,15}\b"),
]

_EMAIL_PATTERN = re.compile(
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
    re.IGNORECASE,
)


def contains_contact_info(text):
    if not text:
        return False
    t = str(text).strip()
    if not t:
        return False
    if _EMAIL_PATTERN.search(t):
        return True
    return any(p.search(t) for p in _PHONE_PATTERNS)


# ============================================================
# LISTING
# ============================================================
class DealListingSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    category_slug = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "description", "price", "location",
            "status", "category_name", "category_slug",
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
# USER
# ============================================================
class DealUserSerializer(serializers.ModelSerializer):
    phone = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "phone", "email"]
        read_only_fields = fields

    def _is_participant(self):
        """
        Mawasiliano ni huru: mnunuzi na muuzaji wa Deal Room hii wanaweza
        kuonana (phone/email) bila kusubiri Reservation Fee.
        Privacy settings (show_phone / show_email) bado zinaheshimiwa.
        """
        request = self.context.get("request")
        deal_room = self.context.get("deal_room")
        if not request or not request.user.is_authenticated:
            return False
        if not deal_room:
            return False
        return request.user.id in [deal_room.buyer_id, deal_room.seller_id]

    def _is_self_or_staff(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return request.user.id == obj.id or request.user.is_staff

    def _prefs(self, obj):
        try:
            return obj.preferences
        except Exception:
            return None

    def get_phone(self, obj):
        if self._is_self_or_staff(obj):
            return getattr(obj, "phone", None)
        if not self._is_participant():
            return None
        prefs = self._prefs(obj)
        if prefs is not None and not prefs.show_phone:
            return None
        return getattr(obj, "phone", None)

    def get_email(self, obj):
        if self._is_self_or_staff(obj):
            return getattr(obj, "email", None)
        if not self._is_participant():
            return None
        prefs = self._prefs(obj)
        if prefs is not None and not prefs.show_email:
            return None
        return getattr(obj, "email", None)


# ============================================================
# OFFERS
# ============================================================
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
    responded_to = serializers.IntegerField(required=False, allow_null=True)

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError(
                "Kiasi cha offer lazima kiwe zaidi ya sifuri."
            )
        return value

    def validate_message(self, value):
        value = (value or "").strip()
        if not value:
            return value
        deal_room = self.context.get("deal_room")
        request = self.context.get("request")
        if not deal_room or not request or not request.user.is_authenticated:
            return value
        # Mawasiliano ni huru — hakuna tena kuzuia namba/email kwenye offer.
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
            DealRoom.Status.OPEN, DealRoom.Status.NEGOTIATING,
        ]:
            raise serializers.ValidationError(
                "Deal Room hii haipokei offers mpya."
            )
        if request.user.id not in [deal_room.buyer_id, deal_room.seller_id]:
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
                    "responded_to": "Offer uliyochagua haipo kwenye Deal Room hii."
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


class DealMessageSerializer(serializers.ModelSerializer):
    """Ujumbe wa chat ndani ya Deal Room (hauhusiani na Messaging app)."""
    sender_id = serializers.IntegerField(read_only=True)
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = DealMessage
        fields = ["id", "sender_id", "sender_name", "text", "created_at"]
        read_only_fields = fields

    def get_sender_name(self, obj):
        return getattr(obj.sender, "name", "")


class DealMessageCreateSerializer(serializers.Serializer):
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
        deal_room = self.context.get("deal_room")
        request = self.context.get("request")
        if not deal_room:
            raise serializers.ValidationError("Deal Room haijapatikana.")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Ni lazima uwe umeingia kwenye akaunti."
            )
        if request.user.id not in [deal_room.buyer_id, deal_room.seller_id]:
            raise serializers.ValidationError(
                "Huruhusiwi kutuma ujumbe kwenye Deal Room hii."
            )
        # Mawasiliano ni huru — hakuna tena kuzuia namba/email kwenye chat.
        return attrs


# ============================================================
# DEAL ROOM LIST
# ============================================================
class DealRoomListSerializer(serializers.ModelSerializer):
    listing = DealListingSerializer(read_only=True)
    buyer = DealUserSerializer(read_only=True)
    seller = DealUserSerializer(read_only=True)

    listing_title = serializers.CharField(source="listing.title", read_only=True)
    listing_price = serializers.DecimalField(
        source="listing.price", max_digits=15, decimal_places=2, read_only=True,
    )
    category = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    latest_offer = serializers.SerializerMethodField()

    # ── MPYA: transaction_id ──
    transaction_id = serializers.SerializerMethodField()

    # ── MPYA: reservation fields ──
    reservation_fee = serializers.SerializerMethodField()
    reservation_hours = serializers.SerializerMethodField()
    reservation_method = serializers.SerializerMethodField()
    reservation_paid_at = serializers.SerializerMethodField()
    reservation_expires_at = serializers.SerializerMethodField()

    # ── MPYA: contact + inspection ──
    can_see_contact = serializers.SerializerMethodField()
    inspection_started_at = serializers.SerializerMethodField()
    inspection_expires_at = serializers.SerializerMethodField()
    inspection_status = serializers.SerializerMethodField()

    class Meta:
        model = DealRoom
        fields = [
            "id", "listing", "listing_title", "listing_price",
            "category", "location",
            "buyer", "seller",
            "status", "agreed_price", "agreed_at", "latest_offer",
            # ── MPYA ──
            "transaction_id",
            "reservation_fee", "reservation_hours",
            "reservation_method", "reservation_paid_at",
            "reservation_expires_at",
            "can_see_contact",
            "inspection_started_at", "inspection_expires_at",
            "inspection_status",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_transaction_id(self, obj):
        try:
            txn = obj.transaction
            return txn.id if txn else None
        except Exception:
            return None

    def get_reservation_fee(self, obj):
        try:
            r = obj.transaction.reservation
            return str(r.deposit_amount) if r else None
        except Exception:
            return None

    def get_reservation_hours(self, obj):
        try:
            r = obj.transaction.reservation
            return getattr(r, "duration_hours", None) if r else None
        except Exception:
            return None

    def get_reservation_method(self, obj):
        try:
            r = obj.transaction.reservation
            return getattr(r, "payment_method", None) if r else None
        except Exception:
            return None

    def get_reservation_paid_at(self, obj):
        try:
            r = obj.transaction.reservation
            return getattr(r, "paid_at", None) if r else None
        except Exception:
            return None

    def get_reservation_expires_at(self, obj):
        try:
            r = obj.transaction.reservation
            return getattr(r, "expires_at", None) if r else None
        except Exception:
            return None

    def get_can_see_contact(self, obj):
        # Washiriki wa Deal Room wanaweza kuonana wakati wowote.
        return True

    def get_inspection_started_at(self, obj):
        try:
            i = obj.transaction.inspection_period
            return getattr(i, "starts_at", None) if i else None
        except Exception:
            return None

    def get_inspection_expires_at(self, obj):
        try:
            i = obj.transaction.inspection_period
            return getattr(i, "expires_at", None) if i else None
        except Exception:
            return None

    def get_inspection_status(self, obj):
        try:
            i = obj.transaction.inspection_period
            return getattr(i, "status", None) if i else None
        except Exception:
            return None

    def get_category(self, obj):
        try:
            return obj.listing.category.name if obj.listing and obj.listing.category else ""
        except Exception:
            return ""

    def get_location(self, obj):
        try:
            return obj.listing.location if obj.listing else ""
        except Exception:
            return ""

    def get_latest_offer(self, obj):
        try:
            offers = list(obj.offers.all())
        except Exception:
            return None
        if not offers:
            return None
        offers.sort(key=lambda o: o.created_at, reverse=True)
        return NegotiationOfferSerializer(
            offers[0], context={**self.context, "deal_room": obj},
        ).data

# ============================================================
# DEAL ROOM DETAIL
# ============================================================
class DealRoomDetailSerializer(serializers.ModelSerializer):
    listing = DealListingSerializer(read_only=True)
    buyer = DealUserSerializer(read_only=True)
    seller = DealUserSerializer(read_only=True)
    offers = NegotiationOfferSerializer(many=True, read_only=True)
    messages = serializers.SerializerMethodField()
    offer_count = serializers.SerializerMethodField()
    latest_offer = serializers.SerializerMethodField()
    deal_room_id = serializers.IntegerField(source="id", read_only=True)
    transaction_id = serializers.SerializerMethodField()
    payment_proof = serializers.SerializerMethodField()
    reservation_fee = serializers.SerializerMethodField()
    reservation_hours = serializers.SerializerMethodField()
    reservation_method = serializers.SerializerMethodField()
    reservation_expires_at = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()

    # ── MPYA ──
    can_see_contact = serializers.SerializerMethodField()
    inspection_started_at = serializers.SerializerMethodField()
    inspection_expires_at = serializers.SerializerMethodField()
    inspection_status = serializers.SerializerMethodField()

    class Meta:
        model = DealRoom
        fields = [
            "id", "deal_room_id",
            "listing", "buyer", "seller",
            "category", "location",
            "status", "agreed_price", "agreed_at",
            "offers", "messages", "offer_count", "latest_offer",
            "transaction_id", "payment_proof",
            "reservation_fee", "reservation_hours",
            "reservation_method", "reservation_expires_at",
            # ── MPYA ──
            "can_see_contact",
            "inspection_started_at", "inspection_expires_at",
            "inspection_status",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def _txn(self, obj):
        return getattr(obj, "transaction", None)

    def _reservation(self, obj):
        txn = self._txn(obj)
        return getattr(txn, "reservation", None) if txn else None

    def _inspection(self, obj):
        txn = self._txn(obj)
        return getattr(txn, "inspection_period", None) if txn else None

    def get_category(self, obj):
        try:
            return obj.listing.category.name if obj.listing and obj.listing.category else ""
        except Exception:
            return ""

    def get_location(self, obj):
        try:
            return obj.listing.location if obj.listing else ""
        except Exception:
            return ""

    def get_transaction_id(self, obj):
        txn = self._txn(obj)
        return txn.id if txn else None

    def get_payment_proof(self, obj):
        txn = self._txn(obj)
        if not txn:
            return None
        proof = getattr(txn, "final_payment_proof", None)
        if not proof:
            return None
        request = self.context.get("request")
        try:
            url = request.build_absolute_uri(proof.url) if request else proof.url
        except Exception:
            url = None
        return {
            "url": url,
            "data_url": url,
            "method": "Bank/Card",
            "reference": txn.final_payment_reference or "",
            "submitted_at": txn.final_payment_uploaded_at,
            "uploaded_at": txn.final_payment_uploaded_at,
            "confirmed": txn.seller_confirmed_payment,
            "confirmed_at": txn.seller_confirmed_at,
        }

    def get_reservation_fee(self, obj):
        r = self._reservation(obj)
        try:
            return str(r.deposit_amount) if r else None
        except Exception:
            return None

    def get_reservation_hours(self, obj):
        r = self._reservation(obj)
        return getattr(r, "duration_hours", None) if r else None

    def get_reservation_method(self, obj):
        r = self._reservation(obj)
        return getattr(r, "payment_method", None) if r else None

    def get_reservation_expires_at(self, obj):
        r = self._reservation(obj)
        return getattr(r, "expires_at", None) if r else None

    # ── MPYA: can_see_contact ──
    def get_can_see_contact(self, obj):
        """
        True kama reservation imelipwa — buyer/seller wanaweza kuonana
        (phone/email) na kuwasiliana wakati wa inspection.
        """
        return True

    # ── MPYA: inspection fields ──
    def get_inspection_started_at(self, obj):
        i = self._inspection(obj)
        return getattr(i, "starts_at", None) if i else None

    def get_inspection_expires_at(self, obj):
        i = self._inspection(obj)
        return getattr(i, "expires_at", None) if i else None

    def get_inspection_status(self, obj):
        i = self._inspection(obj)
        return getattr(i, "status", None) if i else None

    def get_messages(self, obj):
        qs = obj.messages.select_related("sender").order_by("created_at")
        return DealMessageSerializer(qs, many=True).data

    def get_offer_count(self, obj):
        try:
            return len(obj.offers.all())
        except Exception:
            return 0

    def get_latest_offer(self, obj):
        try:
            offers = list(obj.offers.all())
        except Exception:
            return None
        if not offers:
            return None
        offers.sort(key=lambda o: o.created_at, reverse=True)
        return NegotiationOfferSerializer(
            offers[0], context={**self.context, "deal_room": obj},
        ).data


# ============================================================
# DEAL ROOM CREATE
# ============================================================
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

        if listing.status != Listing.Status.LIVE:
            raise serializers.ValidationError(
                "Deal Room inaweza kuanzishwa kwa tangazo lililo AVAILABLE pekee."
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
        self._existing_deal_room = existing
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


# ============================================================
# CANCEL
# ============================================================
class DealRoomCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=True, max_length=500,
    )

    def validate_reason(self, value):
        return value.strip()


# ============================================================
# ACCEPT OFFER
# ============================================================
class DealRoomAcceptOfferSerializer(serializers.Serializer):
    offer_id = serializers.IntegerField(required=True)

    def validate_offer_id(self, value):
        deal_room = self.context.get("deal_room")
        if not deal_room:
            raise serializers.ValidationError("Deal Room haijapatikana.")
        try:
            offer = NegotiationOffer.objects.get(pk=value, deal_room=deal_room)
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
                "Offer hii haiwezi kukubaliwa kwa sababu hali yake si PENDING."
            )
        if deal_room.status not in [
            DealRoom.Status.OPEN, DealRoom.Status.NEGOTIATING,
        ]:
            raise serializers.ValidationError(
                "Deal Room hii haiwezi kukubali offer."
            )
        return value