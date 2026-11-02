from django.utils.translation import gettext as _, override

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from ._lang import user_lang


def notify_deal_room_created(*, deal_room):
    recipient = deal_room.seller
    lang = user_lang(recipient)
    with override(lang):
        create_notification(
            recipient=recipient,
            notification_type=Notification.NotificationType.GENERAL,
            title=_("Deal Room Mpya"),
            message=_(
                "{buyer} ameanza Deal Room kwa tangazo lako '{title}'."
            ).format(
                buyer=deal_room.buyer.name,
                title=deal_room.listing.title,
            ),
            priority=Notification.Priority.NORMAL,
            related_object_type="DealRoom",
            related_object_id=deal_room.id,
            action_url=f"/deals/{deal_room.id}",
        )


def notify_new_offer(*, deal_room, offer):
    if offer.offered_by_id == deal_room.buyer_id:
        recipient = deal_room.seller
        sender_role_key = "buyer"
        notification_type = Notification.NotificationType.NEW_OFFER
        title_key = "new_offer"
    else:
        recipient = deal_room.buyer
        sender_role_key = "seller"
        notification_type = Notification.NotificationType.OFFER_COUNTERED
        title_key = "counter_offer"

    lang = user_lang(recipient)
    with override(lang):
        sender_role = (
            _("Mnunuzi") if sender_role_key == "buyer" else _("Muuzaji")
        )
        title = (
            _("Offer Mpya") if title_key == "new_offer"
            else _("Counter-offer Mpya")
        )

        if offer.responded_to_id:
            message = _(
                "{role} ametuma counter-offer ya TZS {amount} kwenye "
                "Deal Room ya '{title}'."
            ).format(
                role=sender_role,
                amount=f"{offer.amount:,.2f}",
                title=deal_room.listing.title,
            )
        else:
            message = _(
                "{role} ametuma offer ya TZS {amount} kwenye "
                "Deal Room ya '{title}'."
            ).format(
                role=sender_role,
                amount=f"{offer.amount:,.2f}",
                title=deal_room.listing.title,
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
    for recipient in (deal_room.buyer, deal_room.seller):
        lang = user_lang(recipient)
        with override(lang):
            create_notification(
                recipient=recipient,
                notification_type=Notification.NotificationType.OFFER_ACCEPTED,
                title=_("Offer Imekubaliwa"),
                message=_(
                    "Offer ya TZS {amount} imekubaliwa kwa tangazo "
                    "'{title}'. Deal Room sasa iko tayari kuendelea "
                    "kwenye transaction."
                ).format(
                    amount=f"{offer.amount:,.2f}",
                    title=deal_room.listing.title,
                ),
                priority=Notification.Priority.URGENT,
                related_object_type="DealRoom",
                related_object_id=deal_room.id,
                action_url=f"/deals/{deal_room.id}",
            )


def notify_offer_rejected(*, deal_room, offer):
    """
    Notify the offerer that their offer was rejected because
    another offer on the same Deal Room won.
    """
    recipient = offer.offered_by
    lang = user_lang(recipient)
    with override(lang):
        create_notification(
            recipient=recipient,
            notification_type=Notification.NotificationType.OFFER_COUNTERED,
            title=_("Offer Yako Imekataliwa"),
            message=_(
                "Offer yako ya TZS {amount} kwenye Deal Room ya "
                "'{title}' haikuchaguliwa."
            ).format(
                amount=f"{offer.amount:,.2f}",
                title=deal_room.listing.title,
            ),
            priority=Notification.Priority.HIGH,
            related_object_type="DealRoom",
            related_object_id=deal_room.id,
            action_url=f"/deals/{deal_room.id}",
        )


def notify_deal_room_cancelled(*, deal_room, cancelled_by, reason=""):
    if cancelled_by.id == deal_room.buyer_id:
        recipient = deal_room.seller
        cancelled_by_role_key = "buyer"
    else:
        recipient = deal_room.buyer
        cancelled_by_role_key = "seller"

    lang = user_lang(recipient)
    with override(lang):
        cancelled_by_role = (
            _("Mnunuzi") if cancelled_by_role_key == "buyer"
            else _("Muuzaji")
        )

        message = _(
            "{role} amefunga Deal Room ya '{title}'."
        ).format(
            role=cancelled_by_role,
            title=deal_room.listing.title,
        )
        if reason:
            message += " " + _("Sababu: {reason}").format(reason=reason)

        create_notification(
            recipient=recipient,
            notification_type=Notification.NotificationType.GENERAL,
            title=_("Deal Room Imefungwa"),
            message=message,
            priority=Notification.Priority.HIGH,
            related_object_type="DealRoom",
            related_object_id=deal_room.id,
            action_url=f"/deals/{deal_room.id}",
        )


def notify_deal_room_reopened(*, deal_room, reopened_by, note=""):
    """
    Notify the other party that the Deal Room was reopened.
    The reopener already knows — only the counterparty gets notified.
    """
    if reopened_by.id == deal_room.buyer_id:
        recipient = deal_room.seller
        reopened_by_role_key = "buyer"
    else:
        recipient = deal_room.buyer
        reopened_by_role_key = "seller"

    lang = user_lang(recipient)
    with override(lang):
        reopened_by_role = (
            _("Mnunuzi") if reopened_by_role_key == "buyer"
            else _("Muuzaji")
        )

        message = _(
            "{role} amefufua Deal Room ya '{title}'. "
            "Mazungumzo yenu yote yamehifadhiwa — mnaendelea "
            "kujadiliana kutoka mlipoishia."
        ).format(
            role=reopened_by_role,
            title=deal_room.listing.title,
        )
        if note:
            message += " " + _("Ujumbe: {note}").format(note=note)

        create_notification(
            recipient=recipient,
            notification_type=Notification.NotificationType.GENERAL,
            title=_("Deal Room Imefufuliwa"),
            message=message,
            priority=Notification.Priority.HIGH,
            related_object_type="DealRoom",
            related_object_id=deal_room.id,
            action_url=f"/deals/{deal_room.id}",
        )