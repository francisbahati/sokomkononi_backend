# apps/deals/services/notifications.py
from django.utils.translation import gettext as _, override

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

from ._lang import user_lang


# ============================================================
# HELPERS
# ============================================================
def _notify_both(
    *,
    deal_room,
    notification_type,
    title_fn,
    message_fn,
    priority=Notification.Priority.HIGH,
    action_url=None,
):
    """
    Tuma arifa kwa pande ZOTE MBILI (buyer + seller) kwa lugha yao.

    `title_fn(lang)` na `message_fn(lang)` zinapokea lang na kurudisha
    string tayari. Hii inaturuhusu kutafsiri kwa kila mtu kwa lugha yake.

    Arifa moja ikishindwa, nyingine inaendelea.
    """
    if action_url is None:
        action_url = f"/deals/{deal_room.id}"

    for recipient in (deal_room.buyer, deal_room.seller):
        lang = user_lang(recipient)
        try:
            with override(lang):
                create_notification(
                    recipient=recipient,
                    notification_type=notification_type,
                    title=title_fn(lang),
                    message=message_fn(lang),
                    priority=priority,
                    related_object_type="DealRoom",
                    related_object_id=deal_room.id,
                    action_url=action_url,
                )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to notify user %s about deal_room %s",
                getattr(recipient, "id", "?"), deal_room.id,
            )


# ============================================================
# EXISTING NOTIFICATIONS (hazijabadilishwa)
# ============================================================
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
    """
    Arifa kwa upande MMOJA tu (yule ambaye hakughairi).

    Hii inatumika wakati buyer au seller anaghairi. Kwa admin,
    tumia `notify_deal_room_cancelled_by_admin` (inawajulisha wote).
    """
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


# ============================================================
# MPYA — ADMIN MODERATION NOTIFICATIONS
# ============================================================
def notify_admin_message(*, deal_room, text):
    """
    Admin ametuma ujumbe ndani ya room — pande zote mbili zinaarifiwa.
    Ujumbe mfupi wa admin unaingizwa kwenye arifa ili watumiaji
    waone kiini bila kufungua room.
    """
    short_text = text if len(text) <= 160 else text[:157] + "..."

    _notify_both(
        deal_room=deal_room,
        notification_type=Notification.NotificationType.GENERAL,
        title_fn=lambda lang: (
            _("Ujumbe kutoka SokoMkononi Admin")
            if lang == "sw" else "Message from SokoMkononi Admin"
        ),
        message_fn=lambda lang: (
            _(
                "Msimamizi ametuma ujumbe kwenye Deal Room ya '{title}': "
                "'{snippet}'"
            ).format(title=deal_room.listing.title, snippet=short_text)
            if lang == "sw" else
            (
                f"An administrator has sent a message in the Deal Room "
                f"for '{deal_room.listing.title}': '{short_text}'"
            )
        ),
        priority=Notification.Priority.HIGH,
    )


def notify_deal_room_locked(*, deal_room, reason, locked_by=None):
    """
    Room imesimamishwa na admin — pande zote mbili zinaarifiwa na sababu.
    Ujumbe na ofa zinasimama hadi admin afungue.
    """
    _notify_both(
        deal_room=deal_room,
        notification_type=Notification.NotificationType.GENERAL,
        title_fn=lambda lang: (
            _("Deal Room Imesimamishwa") if lang == "sw"
            else "Deal Room Suspended"
        ),
        message_fn=lambda lang: (
            _(
                "Deal Room ya '{title}' imesimamishwa kwa muda na "
                "msimamizi. Sababu: {reason}. Ujumbe na ofa hazitapokelewa "
                "hadi ukaguzi ukamilike."
            ).format(title=deal_room.listing.title, reason=reason)
            if lang == "sw" else
            (
                f"The Deal Room for '{deal_room.listing.title}' has been "
                f"temporarily suspended by an administrator. Reason: "
                f"{reason}. Messages and offers will not be accepted "
                f"until the review is complete."
            )
        ),
        priority=Notification.Priority.URGENT,
    )


def notify_deal_room_unlocked(*, deal_room, unlocked_by=None):
    """
    Room imefunguliwa na admin — pande zote mbili zinaarifiwa.
    """
    _notify_both(
        deal_room=deal_room,
        notification_type=Notification.NotificationType.GENERAL,
        title_fn=lambda lang: (
            _("Deal Room Imefunguliwa") if lang == "sw"
            else "Deal Room Reopened"
        ),
        message_fn=lambda lang: (
            _(
                "Deal Room ya '{title}' imefunguliwa na msimamizi. "
                "Mnaweza kuendelea kutuma ujumbe na ofa."
            ).format(title=deal_room.listing.title)
            if lang == "sw" else
            (
                f"The Deal Room for '{deal_room.listing.title}' has been "
                f"reopened by an administrator. You can continue sending "
                f"messages and offers."
            )
        ),
        priority=Notification.Priority.HIGH,
    )


def notify_deal_room_cancelled_by_admin(*, deal_room, reason, cancelled_by=None):
    """
    Admin ameghairi Deal Room — pande zote mbili zinaarifiwa.
    Sababu ni lazima na inaonekana kwenye arifa.

    Kumbuka: Deal iliyoghairiwa na admin HAIWEZI kufufuliwa na
    mtumiaji (cancelled_by_admin=True). Ujumbe unaeleza hilo.
    """
    _notify_both(
        deal_room=deal_room,
        notification_type=Notification.NotificationType.GENERAL,
        title_fn=lambda lang: (
            _("Deal Room Imefutwa na Msimamizi") if lang == "sw"
            else "Deal Room Cancelled by Admin"
        ),
        message_fn=lambda lang: (
            _(
                "Deal Room ya '{title}' imefutwa na msimamizi. "
                "Sababu: {reason}. Mazungumzo hayawezi kufufuliwa — "
                "wasiliana na support@sokomkononi.co.tz ukihitaji msaada."
            ).format(title=deal_room.listing.title, reason=reason)
            if lang == "sw" else
            (
                f"The Deal Room for '{deal_room.listing.title}' has been "
                f"cancelled by an administrator. Reason: {reason}. "
                f"This conversation cannot be reopened — contact "
                f"support@sokomkononi.co.tz if you need help."
            )
        ),
        priority=Notification.Priority.URGENT,
    )