# apps/transactions/services/notifications.py

from django.utils.translation import gettext as _, override

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from ..models import Transaction
from ._lang import user_lang


def _deal_kwargs(transaction, recipient):
    """
    Frontend inafungua deals kwa DEAL ROOM id (si transaction id),
    na njia hutofautiana kwa buyer/seller. `side` inamwambia frontend
    notification ni ya dashboard ipi.
    """
    is_buyer = recipient.id == transaction.buyer_id
    prefix = "/dashboard/buyer" if is_buyer else "/dashboard"
    deal_id = transaction.deal_room_id
    return {
        "related_object_type": "deal",
        "related_object_id": deal_id,
        "action_url": f"{prefix}/deals?deal={deal_id}",
        "side": "buyer" if is_buyer else "seller",
    }


# ============================================================================
# TRANSACTION CREATED
# ============================================================================

def notify_transaction_created(*, transaction):
    for recipient in (transaction.buyer, transaction.seller):
        lang = user_lang(recipient)
        with override(lang):
            create_notification(
                recipient=recipient,
                notification_type=(
                    Notification.NotificationType.TRANSACTION_CREATED
                ),
                title=_("Transaction Imeundwa"),
                message=_(
                    "Transaction #{id} imeundwa kwa tangazo "
                    "'{title}'. Bei iliyokubaliwa ni TZS {price}."
                ).format(
                    id=transaction.id,
                    title=transaction.listing.title,
                    price=f"{transaction.agreed_price:,.2f}",
                ),
                priority=Notification.Priority.HIGH,
                **_deal_kwargs(transaction, recipient),
            )


# ============================================================================
# BUYER DECISION
# ============================================================================

def notify_buyer_decision(*, transaction):
    decision_labels = {
        Transaction.BuyerDecision.READY_FOR_FINAL_PAYMENT:
            _("Tayari kwa malipo ya mwisho"),
        Transaction.BuyerDecision.NOT_AS_DESCRIBED:
            _("Bidhaa haifanani na maelezo"),
        Transaction.BuyerDecision.REQUEST_NEGOTIATION:
            _("Anaomba mazungumzo zaidi"),
        Transaction.BuyerDecision.CANCEL_TRANSACTION:
            _("Anataka kughairi Transaction"),
    }

    recipient = transaction.seller
    lang = user_lang(recipient)
    with override(lang):
        decision_text = decision_labels.get(
            transaction.buyer_decision,
            transaction.buyer_decision,
        )

        message = _(
            "Mnunuzi ametoa uamuzi wa inspection kwenye "
            "Transaction #{id}: {decision}."
        ).format(id=transaction.id, decision=decision_text)

        if transaction.buyer_decision_note:
            message += " " + _("Maelezo: {note}").format(
                note=transaction.buyer_decision_note,
            )

        create_notification(
            recipient=recipient,
            notification_type=Notification.NotificationType.BUYER_DECISION,
            title=_("Uamuzi wa Mnunuzi"),
            message=message,
            priority=Notification.Priority.URGENT,
            **_deal_kwargs(transaction, recipient),
        )


# ============================================================================
# PAYMENT PROOF UPLOADED
# ============================================================================

def notify_payment_proof_uploaded(*, transaction):
    recipient = transaction.seller
    lang = user_lang(recipient)
    with override(lang):
        message = _(
            "Mnunuzi amepakia ushahidi wa malipo ya mwisho "
            "kwa Transaction #{id}. Tafadhali hakikisha umepokea "
            "malipo kabla ya kuyathibitisha."
        ).format(id=transaction.id)

        if transaction.final_payment_reference:
            message += " " + _("Reference: {ref}.").format(
                ref=transaction.final_payment_reference,
            )

        create_notification(
            recipient=recipient,
            notification_type=(
                Notification.NotificationType.PAYMENT_PROOF_UPLOADED
            ),
            title=_("Ushahidi wa Malipo Umewekwa"),
            message=message,
            priority=Notification.Priority.URGENT,
            **_deal_kwargs(transaction, recipient),
        )


# ============================================================================
# PAYMENT CONFIRMED
# ============================================================================

def notify_payment_confirmed(*, transaction):
    recipient = transaction.buyer
    lang = user_lang(recipient)
    with override(lang):
        create_notification(
            recipient=recipient,
            notification_type=(
                Notification.NotificationType.PAYMENT_CONFIRMED
            ),
            title=_("Malipo Yamethibitishwa"),
            message=_(
                "Muuzaji amethibitisha kupokea malipo ya mwisho "
                "kwa Transaction #{id}."
            ).format(id=transaction.id),
            priority=Notification.Priority.HIGH,
            **_deal_kwargs(transaction, recipient),
        )


# ============================================================================
# TRANSACTION COMPLETED
# ============================================================================

def notify_transaction_completed(*, transaction):
    for recipient in (transaction.buyer, transaction.seller):
        lang = user_lang(recipient)
        with override(lang):
            create_notification(
                recipient=recipient,
                notification_type=(
                    Notification.NotificationType.TRANSACTION_COMPLETED
                ),
                title=_("Transaction Imekamilika"),
                message=_(
                    "Transaction #{id} ya '{title}' imekamilika. "
                    "Tangazo sasa limewekwa SOLD."
                ).format(
                    id=transaction.id,
                    title=transaction.listing.title,
                ),
                priority=Notification.Priority.URGENT,
                **_deal_kwargs(transaction, recipient),
            )


# ============================================================================
# TRANSACTION CANCELLED
# ============================================================================

def notify_transaction_cancelled(*, transaction, cancelled_by, reason):
    if cancelled_by.id == transaction.buyer_id:
        recipient = transaction.seller
        cancelled_by_role_key = "buyer"
    elif cancelled_by.id == transaction.seller_id:
        recipient = transaction.buyer
        cancelled_by_role_key = "seller"
    else:
        return

    lang = user_lang(recipient)
    with override(lang):
        cancelled_by_role = (
            _("Mnunuzi") if cancelled_by_role_key == "buyer"
            else _("Muuzaji")
        )

        message = _(
            "{role} ameghairi Transaction #{id} ya '{title}'."
        ).format(
            role=cancelled_by_role,
            id=transaction.id,
            title=transaction.listing.title,
        )
        if reason:
            message += " " + _("Sababu: {reason}").format(reason=reason)

        create_notification(
            recipient=recipient,
            notification_type=(
                Notification.NotificationType.TRANSACTION_CANCELLED
            ),
            title=_("Transaction Imeghairiwa"),
            message=message,
            priority=Notification.Priority.HIGH,
            **_deal_kwargs(transaction, recipient),
        )


# ============================================================================
# RESERVATION CREATED
# ============================================================================

def notify_reservation_created(*, reservation):
    transaction = reservation.transaction

    # Buyer
    lang = user_lang(transaction.buyer)
    with override(lang):
        create_notification(
            recipient=transaction.buyer,
            notification_type=(
                Notification.NotificationType.RESERVATION_CREATED
            ),
            title=_("Reservation Imeanzishwa"),
            message=_(
                "Reservation imeanzishwa kwa Transaction #{id} ya "
                "'{title}'. Deposit inayotakiwa ni TZS {deposit}. "
                "Tafadhali kamilisha malipo ya reservation."
            ).format(
                id=transaction.id,
                title=transaction.listing.title,
                deposit=f"{reservation.deposit_amount:,.2f}",
            ),
            priority=Notification.Priority.HIGH,
            **_deal_kwargs(transaction, transaction.buyer),
        )

    # Seller
    lang = user_lang(transaction.seller)
    with override(lang):
        create_notification(
            recipient=transaction.seller,
            notification_type=(
                Notification.NotificationType.RESERVATION_CREATED
            ),
            title=_("Reservation Mpya"),
            message=_(
                "Mnunuzi ameanzisha reservation kwa Transaction #{id} "
                "ya tangazo '{title}'. Inasubiri malipo ya reservation."
            ).format(id=transaction.id, title=transaction.listing.title),
            priority=Notification.Priority.HIGH,
            **_deal_kwargs(transaction, transaction.seller),
        )


# ============================================================================
# RESERVATION PAID
# ============================================================================

def notify_reservation_paid(*, reservation):
    transaction = reservation.transaction

    for recipient in (transaction.buyer, transaction.seller):
        lang = user_lang(recipient)
        with override(lang):
            create_notification(
                recipient=recipient,
                notification_type=(
                    Notification.NotificationType.RESERVATION_PAID
                ),
                title=_("Reservation Imelipwa"),
                message=_(
                    "Malipo ya reservation ya Transaction #{id} "
                    "yamethibitishwa. Reservation ni ya saa {hours} "
                    "na imeanza rasmi."
                ).format(
                    id=transaction.id,
                    hours=reservation.duration_hours,
                ),
                priority=Notification.Priority.URGENT,
                **_deal_kwargs(transaction, recipient),
            )


# ============================================================================
# RESERVATION EXPIRED
# ============================================================================

def notify_reservation_expired(*, reservation):
    transaction = reservation.transaction

    for recipient in (transaction.buyer, transaction.seller):
        lang = user_lang(recipient)
        with override(lang):
            create_notification(
                recipient=recipient,
                notification_type=(
                    Notification.NotificationType.RESERVATION_EXPIRED
                ),
                title=_("Reservation Imeisha"),
                message=_(
                    "Reservation ya Transaction #{id} ya '{title}' "
                    "imeisha muda. Transaction imefungwa na tangazo "
                    "limerudishwa kwenye hali ya AVAILABLE."
                ).format(
                    id=transaction.id,
                    title=transaction.listing.title,
                ),
                priority=Notification.Priority.URGENT,
                **_deal_kwargs(transaction, recipient),
            )


# ============================================================================
# INSPECTION STARTED
# ============================================================================

def notify_inspection_started(*, inspection):
    transaction = inspection.transaction

    for recipient in (transaction.buyer, transaction.seller):
        lang = user_lang(recipient)
        with override(lang):
            create_notification(
                recipient=recipient,
                notification_type=(
                    Notification.NotificationType.INSPECTION_STARTED
                ),
                title=_("Inspection Imeanza"),
                message=_(
                    "Inspection ya Transaction #{id} imeanza. "
                    "Muda wa inspection ni saa {hours}. "
                    "Tafadhali kamilisha ukaguzi kabla ya muda kuisha."
                ).format(
                    id=transaction.id,
                    hours=inspection.duration_hours,
                ),
                priority=Notification.Priority.HIGH,
                **_deal_kwargs(transaction, recipient),
            )


# ============================================================================
# INSPECTION COMPLETED
# ============================================================================

def notify_inspection_completed(*, inspection):
    transaction = inspection.transaction

    for recipient in (transaction.buyer, transaction.seller):
        lang = user_lang(recipient)
        with override(lang):
            message = _(
                "Inspection ya Transaction #{id} imekamilika."
            ).format(id=transaction.id)

            if transaction.buyer_decision == Transaction.BuyerDecision.PENDING:
                message += " " + _(
                    "Mnunuzi bado hajatoa uamuzi wa inspection."
                )

            create_notification(
                recipient=recipient,
                notification_type=(
                    Notification.NotificationType.INSPECTION_COMPLETED
                ),
                title=_("Inspection Imekamilika"),
                message=message,
                priority=Notification.Priority.HIGH,
                **_deal_kwargs(transaction, recipient),
            )