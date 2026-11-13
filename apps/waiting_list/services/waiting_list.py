import logging

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _, override
from rest_framework.exceptions import APIException, ValidationError

from apps.listings.models import Listing

from ..models import WaitingListEntry
from ._lang import user_lang

logger = logging.getLogger(__name__)


class WaitingListError(APIException):
    """Kosa lenye `detail` + `code` ili frontend ifanye uamuzi bila kulinganisha maandishi."""

    status_code = 400
    default_code = "waiting_list_error"

    def __init__(self, message, *, code=None, status_code=None):
        if status_code:
            self.status_code = status_code
        super().__init__(detail={"detail": message, "code": code or self.default_code})


def get_next_waiting_position(listing):
    # Hesabu NOTIFIED pia — awali ilihesabu WAITING pekee, na mtu mpya angepata
    # position sawa na aliyetaarifiwa (position zinagongana).
    last_entry = (
        WaitingListEntry.objects
        .filter(
            listing=listing,
            status__in=[
                WaitingListEntry.Status.WAITING,
                WaitingListEntry.Status.NOTIFIED,
            ],
        )
        .order_by("-position")
        .first()
    )
    return 1 if not last_entry else last_entry.position + 1


def _send_waiting_list_joined_notification(listing, buyer):
    """
    Tuma notification kwa mtumiaji mpya wa waiting list,
    ikimjulisha muda wa reservation ya sasa.
    """
    try:
        from apps.transactions.models import Reservation
        from apps.notifications.models import Notification
        from apps.notifications.services.notification import create_notification

        reservation = Reservation.objects.filter(
            transaction__listing_id=listing.pk,
            status=Reservation.Status.ACTIVE,
        ).order_by("-created_at").first()

        time_left_minutes = 0
        if reservation and getattr(reservation, "expires_at", None):
            delta = reservation.expires_at - timezone.now()
            time_left_minutes = max(0, int(delta.total_seconds() / 60))

        lang = user_lang(buyer)
        with override(lang):
            create_notification(
                recipient=buyer,
                notification_type=Notification.NotificationType.GENERAL,
                title=_("Umeingia kwenye Waiting List"),
                message=_(
                    "Umejiunga na waiting list ya mali '{title}'. "
                    "Reservation ya sasa inaisha baada ya dakika {minutes}. "
                    "Utapata taarifa endapo itaisha."
                ).format(
                    title=listing.title,
                    minutes=time_left_minutes,
                ),
                priority=Notification.Priority.NORMAL,
                related_object_type="listing",
                related_object_id=listing.id,
                action_url=f"/mali/{listing.id}",
            )
    except Exception:
        logger.exception(
            "Failed to send waiting list notification for listing %s",
            listing.pk,
        )


@transaction.atomic
def join_waiting_list(*, listing, buyer):
    if not buyer.is_authenticated:
        raise ValidationError("Lazima uwe umeingia kwenye akaunti.")
    if not buyer.is_active:
        raise ValidationError("Akaunti yako haijawezeshwa.")
    if not buyer.email_verified:
        raise ValidationError(
            "Thibitisha barua pepe yako kwanza."
        )

    listing = Listing.objects.select_for_update().get(pk=listing.pk)

    if listing.seller_id == buyer.id:
        raise ValidationError(
            "Huwezi kujiunga kwenye waiting list ya tangazo lako."
        )
    if listing.status != Listing.Status.RESERVED:
        raise ValidationError(
            "Waiting list inapatikana kwa tangazo lililo RESERVED pekee."
        )

    existing = WaitingListEntry.objects.filter(
        listing=listing, buyer=buyer,
    ).first()

    if existing:
        if existing.status in [
            WaitingListEntry.Status.WAITING,
            WaitingListEntry.Status.NOTIFIED,
        ]:
            raise ValidationError(
                "Tayari uko kwenye waiting list ya tangazo hili."
            )

        # Re-join: reuse the row.
        existing.status = WaitingListEntry.Status.WAITING
        existing.position = get_next_waiting_position(listing)
        existing.notified_at = None
        existing.respond_by = None
        existing.save(update_fields=[
            "status", "position", "notified_at", "respond_by", "updated_at",
        ])

        # ✅ Tuma notification
        transaction.on_commit(
            lambda: _send_waiting_list_joined_notification(listing, buyer)
        )
        return existing

    position = get_next_waiting_position(listing)

    entry = WaitingListEntry.objects.create(
        listing=listing,
        buyer=buyer,
        status=WaitingListEntry.Status.WAITING,
        position=position,
    )

    # ✅ Tuma notification
    transaction.on_commit(
        lambda: _send_waiting_list_joined_notification(listing, buyer)
    )

    return entry


@transaction.atomic
def leave_waiting_list(*, entry, buyer):
    if entry.buyer_id != buyer.id and not buyer.is_staff:
        raise ValidationError(
            "Huruhusiwi kuondoa entry hii ya waiting list."
        )

    if entry.status in [
        WaitingListEntry.Status.CANCELLED,
        WaitingListEntry.Status.FULFILLED,
    ]:
        raise ValidationError("Entry hii tayari imefungwa.")

    listing_id = entry.listing_id

    entry.status = WaitingListEntry.Status.CANCELLED
    entry.save(update_fields=["status", "updated_at"])

    reorder_waiting_list(listing_id=listing_id)


@transaction.atomic
def reorder_waiting_list(*, listing_id):
    entries = list(
        WaitingListEntry.objects
        .select_for_update()
        .filter(
            listing_id=listing_id,
            status__in=[
                WaitingListEntry.Status.WAITING,
                WaitingListEntry.Status.NOTIFIED,
            ],
        )
        # Awali: joined_at — lakini re-join inatumia row ile ile (joined_at ya zamani),
        # kwa hiyo aliyerudi alirukia mbele ya foleni. Position ndiyo chanzo cha ukweli.
        .order_by("position", "joined_at", "id")
    )

    for position, entry in enumerate(entries, start=1):
        if entry.position != position:
            entry.position = position
            entry.save(update_fields=["position", "updated_at"])


@transaction.atomic
def fulfil_waiting_entry(*, entry):
    entry = WaitingListEntry.objects.select_for_update().get(pk=entry.pk)

    if entry.status == WaitingListEntry.Status.FULFILLED:
        return entry

    entry.status = WaitingListEntry.Status.FULFILLED
    entry.save(update_fields=["status", "updated_at"])
    return entry


@transaction.atomic
def claim_waitlist_entry(*, entry, user, duration_hours=None):
    """
    Buyer claims a NOTIFIED waitlist slot and starts a reservation.

    Single source of truth — view ya `claim` inaita hii (awali view ilikuwa na
    nakala yake isiyo na lock, na hii ilikuwa na saa 24 zisizobadilika).
    Makosa yana `code`: forbidden | not_notified | expired |
    listing_unavailable | deal_room_required | invalid_duration | reservation_failed
    """
    entry = (
        WaitingListEntry.objects
        .select_for_update(of=("self",))
        .select_related("listing", "buyer")
        .get(pk=entry.pk)
    )

    if entry.buyer_id != user.id:
        raise WaitingListError("Huna ruhusa.", code="forbidden", status_code=403)
    if entry.status != WaitingListEntry.Status.NOTIFIED:
        raise WaitingListError(
            "Nafasi yako bado haijafunguliwa. "
            "Subiri taarifa ya kukamilisha reservation.",
            code="not_notified", status_code=409,
        )
    if entry.respond_by and entry.respond_by <= timezone.now():
        raise WaitingListError(
            "Muda wa kuchukua nafasi umepita.", code="expired", status_code=409,
        )
    if entry.listing.status != Listing.Status.LIVE:
        raise WaitingListError(
            "Tangazo halipo tena.", code="listing_unavailable", status_code=409,
        )

    from apps.deals.models import DealRoom
    from apps.transactions.models import Transaction
    from apps.transactions.services.reservation import (
        create_reservation,
        get_allowed_reservation_hours,
    )

    dr = DealRoom.objects.filter(
        listing=entry.listing, buyer=user,
    ).order_by("-created_at").first()
    if not dr:
        raise WaitingListError(
            "Anzisha mazungumzo (Deal Room) na muuzaji kwanza ili kuweka reservation.",
            code="deal_room_required",
        )

    # Muda: tier yoyote hai (mnunuzi anachagua). Bila chaguo → tier ndogo kuliko zote.
    allowed = sorted(get_allowed_reservation_hours())
    if not allowed:
        raise WaitingListError(
            "Hakuna tiers za reservation zilizo hai.", code="invalid_duration",
        )
    if duration_hours in (None, ""):
        hours = allowed[0]
    else:
        try:
            hours = int(duration_hours)
        except (TypeError, ValueError):
            raise WaitingListError(
                "Muda wa reservation si sahihi.", code="invalid_duration",
            )
        if hours not in allowed:
            raise WaitingListError(
                "Chagua muda mmoja wa saa: " + ", ".join(str(h) for h in allowed),
                code="invalid_duration",
            )

    txn, _created = Transaction.objects.get_or_create(
        deal_room=dr,
        defaults={
            "listing": entry.listing,
            "buyer": user,
            "seller": entry.listing.seller,
            "agreed_price": dr.agreed_price or entry.listing.price,
            "status": Transaction.Status.RESERVATION_PENDING,
        },
    )

    try:
        res = create_reservation(transaction=txn, user=user, duration_hours=hours)
    except ValidationError as exc:
        detail = exc.detail
        if isinstance(detail, (list, tuple)) and detail:
            detail = str(detail[0])
        elif isinstance(detail, dict):
            detail = "; ".join(str(v) for v in detail.values())
        raise WaitingListError(str(detail), code="reservation_failed")

    entry.status = WaitingListEntry.Status.FULFILLED
    entry.save(update_fields=["status", "updated_at"])
    return {"entry": entry, "transaction": txn, "reservation": res}