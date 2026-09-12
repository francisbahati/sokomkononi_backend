
from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from ..models import Transaction


# ============================================================================
# TRANSACTION CREATED
# ============================================================================

def notify_transaction_created(*, transaction):
    """
    Notify buyer and seller when a Transaction is created
    from an AGREED Deal Room.
    """

    message = (
        f"Transaction #{transaction.id} imeundwa kwa tangazo "
        f"'{transaction.listing.title}'. "
        f"Bei iliyokubaliwa ni TZS "
        f"{transaction.agreed_price:,.2f}."
    )

    for recipient in (
        transaction.buyer,
        transaction.seller,
    ):
        create_notification(
            recipient=recipient,
            notification_type=(
                Notification.NotificationType.TRANSACTION_CREATED
            ),
            title="Transaction Imeundwa",
            message=message,
            priority=Notification.Priority.HIGH,
            related_object_type="Transaction",
            related_object_id=transaction.id,
            action_url=f"/transactions/{transaction.id}",
        )


# ============================================================================
# BUYER DECISION
# ============================================================================

def notify_buyer_decision(*, transaction):
    """
    Notify seller when buyer submits a decision after inspection.
    """

    decision_labels = {
        Transaction.BuyerDecision.READY_FOR_FINAL_PAYMENT:
            "Tayari kwa malipo ya mwisho",

        Transaction.BuyerDecision.NOT_AS_DESCRIBED:
            "Bidhaa haifanani na maelezo",

        Transaction.BuyerDecision.REQUEST_NEGOTIATION:
            "Anaomba mazungumzo zaidi",

        Transaction.BuyerDecision.CANCEL_TRANSACTION:
            "Anataka kughairi Transaction",
    }

    decision_text = decision_labels.get(
        transaction.buyer_decision,
        transaction.buyer_decision,
    )

    message = (
        f"Mnunuzi ametoa uamuzi wa inspection kwenye "
        f"Transaction #{transaction.id}: {decision_text}."
    )

    if transaction.buyer_decision_note:
        message += (
            f" Maelezo: {transaction.buyer_decision_note}"
        )

    create_notification(
        recipient=transaction.seller,
        notification_type=Notification.NotificationType.BUYER_DECISION,
        title="Uamuzi wa Mnunuzi",
        message=message,
        priority=Notification.Priority.URGENT,
        related_object_type="Transaction",
        related_object_id=transaction.id,
        action_url=f"/transactions/{transaction.id}",
    )


# ============================================================================
# PAYMENT PROOF UPLOADED
# ============================================================================

def notify_payment_proof_uploaded(*, transaction):
    """
    Notify seller when buyer uploads final payment proof.
    """

    message = (
        f"Mnunuzi amepakia ushahidi wa malipo ya mwisho "
        f"kwa Transaction #{transaction.id}. "
        f"Tafadhali hakikisha umepokea malipo kabla ya "
        f"kuyathibitisha."
    )

    if transaction.final_payment_reference:
        message += (
            f" Reference: {transaction.final_payment_reference}."
        )

    create_notification(
        recipient=transaction.seller,
        notification_type=(
            Notification.NotificationType.PAYMENT_PROOF_UPLOADED
        ),
        title="Ushahidi wa Malipo Umewekwa",
        message=message,
        priority=Notification.Priority.URGENT,
        related_object_type="Transaction",
        related_object_id=transaction.id,
        action_url=f"/transactions/{transaction.id}",
    )


# ============================================================================
# PAYMENT CONFIRMED
# ============================================================================

def notify_payment_confirmed(*, transaction):
    """
    Notify buyer when seller confirms final payment.
    """

    message = (
        f"Muuzaji amethibitisha kupokea malipo ya mwisho "
        f"kwa Transaction #{transaction.id}."
    )

    create_notification(
        recipient=transaction.buyer,
        notification_type=(
            Notification.NotificationType.PAYMENT_CONFIRMED
        ),
        title="Malipo Yamethibitishwa",
        message=message,
        priority=Notification.Priority.HIGH,
        related_object_type="Transaction",
        related_object_id=transaction.id,
        action_url=f"/transactions/{transaction.id}",
    )


# ============================================================================
# TRANSACTION COMPLETED
# ============================================================================

def notify_transaction_completed(*, transaction):
    """
    Notify buyer and seller when the transaction is completed.
    """

    message = (
        f"Transaction #{transaction.id} ya "
        f"'{transaction.listing.title}' imekamilika. "
        f"Tangazo sasa limewekwa SOLD."
    )

    for recipient in (
        transaction.buyer,
        transaction.seller,
    ):
        create_notification(
            recipient=recipient,
            notification_type=(
                Notification.NotificationType.TRANSACTION_COMPLETED
            ),
            title="Transaction Imekamilika",
            message=message,
            priority=Notification.Priority.URGENT,
            related_object_type="Transaction",
            related_object_id=transaction.id,
            action_url=f"/transactions/{transaction.id}",
        )


# ============================================================================
# TRANSACTION CANCELLED
# ============================================================================

def notify_transaction_cancelled(
    *,
    transaction,
    cancelled_by,
    reason,
):
    """
    Notify the other participant when a transaction is cancelled.
    """

    if cancelled_by.id == transaction.buyer_id:
        recipient = transaction.seller
        cancelled_by_role = "Mnunuzi"

    elif cancelled_by.id == transaction.seller_id:
        recipient = transaction.buyer
        cancelled_by_role = "Muuzaji"

    else:
        return

    message = (
        f"{cancelled_by_role} amegairi Transaction "
        f"#{transaction.id} ya '{transaction.listing.title}'."
    )

    if reason:
        message += f" Sababu: {reason}"

    create_notification(
        recipient=recipient,
        notification_type=(
            Notification.NotificationType.TRANSACTION_CANCELLED
        ),
        title="Transaction Imeghairiwa",
        message=message,
        priority=Notification.Priority.HIGH,
        related_object_type="Transaction",
        related_object_id=transaction.id,
        action_url=f"/transactions/{transaction.id}",
    )


# ============================================================================
# RESERVATION CREATED
# ============================================================================

def notify_reservation_created(*, reservation):
    """
    Notify buyer and seller when a reservation is created.

    At this point the reservation is still PENDING_PAYMENT.
    The listing is NOT yet RESERVED.
    """

    transaction = reservation.transaction

    message = (
        f"Reservation imeanzishwa kwa Transaction "
        f"#{transaction.id} ya '{transaction.listing.title}'. "
        f"Deposit inayotakiwa ni TZS "
        f"{reservation.deposit_amount:,.2f}. "
        f"Tafadhali kamilisha malipo ya reservation."
    )

    # Buyer receives confirmation.
    create_notification(
        recipient=transaction.buyer,
        notification_type=(
            Notification.NotificationType.RESERVATION_CREATED
        ),
        title="Reservation Imeanzishwa",
        message=message,
        priority=Notification.Priority.HIGH,
        related_object_type="Reservation",
        related_object_id=reservation.id,
        action_url=f"/transactions/{transaction.id}",
    )

    # Seller is informed that the buyer has started the reservation process.
    seller_message = (
        f"Mnunuzi ameanzisha reservation kwa Transaction "
        f"#{transaction.id} ya tangazo '{transaction.listing.title}'. "
        f"Inasubiri malipo ya reservation."
    )

    create_notification(
        recipient=transaction.seller,
        notification_type=(
            Notification.NotificationType.RESERVATION_CREATED
        ),
        title="Reservation Mpya",
        message=seller_message,
        priority=Notification.Priority.HIGH,
        related_object_type="Reservation",
        related_object_id=reservation.id,
        action_url=f"/transactions/{transaction.id}",
    )


# ============================================================================
# RESERVATION PAID
# ============================================================================

def notify_reservation_paid(*, reservation):
    """
    Notify buyer and seller after reservation deposit is confirmed.
    """

    transaction = reservation.transaction

    message = (
        f"Malipo ya reservation ya Transaction "
        f"#{transaction.id} yamethibitishwa. "
        f"Reservation ni ya saa {reservation.duration_hours} "
        f"na imeanza rasmi."
    )

    for recipient in (
        transaction.buyer,
        transaction.seller,
    ):
        create_notification(
            recipient=recipient,
            notification_type=(
                Notification.NotificationType.RESERVATION_PAID
            ),
            title="Reservation Imelipwa",
            message=message,
            priority=Notification.Priority.URGENT,
            related_object_type="Reservation",
            related_object_id=reservation.id,
            action_url=f"/transactions/{transaction.id}",
        )


# ============================================================================
# RESERVATION EXPIRED
# ============================================================================

def notify_reservation_expired(*, reservation):
    """
    Notify buyer and seller when a reservation expires.
    """

    transaction = reservation.transaction

    message = (
        f"Reservation ya Transaction #{transaction.id} "
        f"ya '{transaction.listing.title}' imeisha muda. "
        f"Transaction imefungwa na tangazo limerudishwa "
        f"kwenye hali ya AVAILABLE."
    )

    for recipient in (
        transaction.buyer,
        transaction.seller,
    ):
        create_notification(
            recipient=recipient,
            notification_type=(
                Notification.NotificationType.RESERVATION_EXPIRED
            ),
            title="Reservation Imeisha",
            message=message,
            priority=Notification.Priority.URGENT,
            related_object_type="Reservation",
            related_object_id=reservation.id,
            action_url=f"/transactions/{transaction.id}",
        )


# ============================================================================
# INSPECTION STARTED
# ============================================================================

def notify_inspection_started(*, inspection):
    """
    Notify buyer and seller when the inspection period starts.
    """

    transaction = inspection.transaction

    message = (
        f"Inspection ya Transaction #{transaction.id} "
        f"imeanza. Muda wa inspection ni saa "
        f"{inspection.duration_hours}. "
        f"Tafadhali kamilisha ukaguzi kabla ya muda kuisha."
    )

    for recipient in (
        transaction.buyer,
        transaction.seller,
    ):
        create_notification(
            recipient=recipient,
            notification_type=(
                Notification.NotificationType.INSPECTION_STARTED
            ),
            title="Inspection Imeanza",
            message=message,
            priority=Notification.Priority.HIGH,
            related_object_type="InspectionPeriod",
            related_object_id=inspection.id,
            action_url=f"/transactions/{transaction.id}",
        )


# ============================================================================
# INSPECTION COMPLETED
# ============================================================================

def notify_inspection_completed(*, inspection):
    """
    Notify buyer and seller when the inspection period ends.
    """

    transaction = inspection.transaction

    message = (
        f"Inspection ya Transaction #{transaction.id} "
        f"imekamilika."
    )

    if transaction.buyer_decision == Transaction.BuyerDecision.PENDING:
        message += (
            " Mnunuzi bado hajatoa uamuzi wa inspection."
        )

    for recipient in (
        transaction.buyer,
        transaction.seller,
    ):
        create_notification(
            recipient=recipient,
            notification_type=(
                Notification.NotificationType.INSPECTION_COMPLETED
            ),
            title="Inspection Imekamilika",
            message=message,
            priority=Notification.Priority.HIGH,
            related_object_type="InspectionPeriod",
            related_object_id=inspection.id,
            action_url=f"/transactions/{transaction.id}",
        )
