from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification


def notify_deal_room_created(*, deal_room):
    """
    Notify the seller when a buyer starts a Deal Room.
    """

    create_notification(
        recipient=deal_room.seller,
        notification_type=Notification.NotificationType.GENERAL,
        title="Deal Room Mpya",
        message=(
            f"{deal_room.buyer.name} ameanza Deal Room "
            f"kwa tangazo lako '{deal_room.listing.title}'."
        ),
        priority=Notification.Priority.NORMAL,
        related_object_type="DealRoom",
        related_object_id=deal_room.id,
        action_url=f"/deals/{deal_room.id}",
    )


def notify_new_offer(*, deal_room, offer):
    """
    Notify the opposite participant when a new offer is submitted.
    """

    if offer.offered_by_id == deal_room.buyer_id:
        recipient = deal_room.seller
        sender_role = "Mnunuzi"
        notification_type = Notification.NotificationType.NEW_OFFER
        title = "Offer Mpya"
    else:
        recipient = deal_room.buyer
        sender_role = "Muuzaji"
        notification_type = Notification.NotificationType.OFFER_COUNTERED
        title = "Counter-offer Mpya"

    if offer.responded_to_id:
        message = (
            f"{sender_role} ametuma counter-offer ya "
            f"TZS {offer.amount:,.2f} kwenye Deal Room ya "
            f"'{deal_room.listing.title}'."
        )
    else:
        message = (
            f"{sender_role} ametuma offer ya "
            f"TZS {offer.amount:,.2f} kwenye Deal Room ya "
            f"'{deal_room.listing.title}'."
        )

    create_notification(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        priority=Notification.Priority.HIGH,
        related_object_type="DealRoom",
        related_object_id=deal_room.id,
        action_url=f"/deals/{deal_room.id}",
    )


def notify_offer_accepted(*, deal_room, offer):
    """
    Notify both buyer and seller when an offer is accepted.
    """

    accepted_message = (
        f"Offer ya TZS {offer.amount:,.2f} imekubaliwa "
        f"kwa tangazo '{deal_room.listing.title}'. "
        f"Deal Room sasa iko tayari kuendelea kwenye transaction."
    )

    participants = [
        deal_room.buyer,
        deal_room.seller,
    ]

    for recipient in participants:
        create_notification(
            recipient=recipient,
            notification_type=Notification.NotificationType.OFFER_ACCEPTED,
            title="Offer Imekubaliwa",
            message=accepted_message,
            priority=Notification.Priority.URGENT,
            related_object_type="DealRoom",
            related_object_id=deal_room.id,
            action_url=f"/deals/{deal_room.id}",
        )


def notify_deal_room_cancelled(*, deal_room, cancelled_by, reason=""):
    """
    Notify the other participant when a Deal Room is cancelled.
    """

    if cancelled_by.id == deal_room.buyer_id:
        recipient = deal_room.seller
        cancelled_by_role = "Mnunuzi"
    else:
        recipient = deal_room.buyer
        cancelled_by_role = "Muuzaji"

    message = (
        f"{cancelled_by_role} amefunga Deal Room ya "
        f"'{deal_room.listing.title}'."
    )

    if reason:
        message += f" Sababu: {reason}"

    create_notification(
        recipient=recipient,
        notification_type=Notification.NotificationType.GENERAL,
        title="Deal Room Imefungwa",
        message=message,
        priority=Notification.Priority.HIGH,
        related_object_type="DealRoom",
        related_object_id=deal_room.id,
        action_url=f"/deals/{deal_room.id}",
    )