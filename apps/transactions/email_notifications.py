# apps/transactions/email_notifications.py
"""
Email notifications kwa transactions app.

- send_reservation_expiring_email
- send_waiting_list_reservation_email
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


# ============================================================
# RESERVATION EXPIRING (buyer)
# ============================================================
def send_reservation_expiring_email(*, buyer, reservation, minutes_left):
    """
    Tuma email kwa buyer kwamba reservation inaisha.

    Returns: True/False
    """
    if not buyer or not buyer.email:
        return False

    try:
        transaction = reservation.transaction
        listing = transaction.listing
    except Exception:
        logger.exception(
            "Missing transaction/listing for reservation %s",
            getattr(reservation, "id", "?"),
        )
        return False

    subject = (
        f"SokoMkononi: Reservation yako inaisha baada ya dakika "
        f"{minutes_left}"
    )

    site_url = getattr(
        settings, "SITE_URL", "https://sokomkononi.co.tz",
    )

    context = {
        "buyer_name": buyer.name or "Mteja",
        "listing_title": listing.title,
        "transaction_id": transaction.id,
        "minutes_left": minutes_left,
        "expires_at": reservation.expires_at,
        "reservation_id": reservation.id,
        "site_url": site_url,
    }

    try:
        text_message = render_to_string(
            "emails/reservation_expiring.txt", context,
        )
    except Exception:
        text_message = (
            f"Habari {context['buyer_name']},\n\n"
            f"Reservation yako ya mali '{context['listing_title']}' "
            f"inaisha baada ya dakika {minutes_left}.\n\n"
            f"Tafadhali renew ili uendelee kureserve, au cancel.\n\n"
            f"Nenda: {site_url}/dashboard/buyer/reservations\n\n"
            f"Asante,\nSokoMkononi"
        )

    try:
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[buyer.email],
            fail_silently=False,
        )
        logger.info(
            "[email] Reservation expiring sent to %s (resv #%s)",
            buyer.email, reservation.id,
        )
        return True
    except Exception:
        logger.exception(
            "Failed to send expiring email for reservation %s",
            reservation.id,
        )
        return False


# ============================================================
# WAITING LIST RESERVATION EXPIRING (buyer)
# ============================================================
def send_waiting_list_reservation_email(*, buyer, listing):
    """
    Tuma email kwa waiting list buyer kwamba reservation
    ya listing wanayosubiri inaisha.

    Returns: True/False
    """
    if not buyer or not buyer.email:
        return False

    subject = (
        f"SokoMkononi: Nafasi inakaribia kufunguka — {listing.title}"
    )

    site_url = getattr(
        settings, "SITE_URL", "https://sokomkononi.co.tz",
    )

    context = {
        "buyer_name": buyer.name or "Mteja",
        "listing_title": listing.title,
        "listing_id": listing.id,
        "site_url": site_url,
    }

    try:
        text_message = render_to_string(
            "emails/waiting_list_reservation_expiring.txt", context,
        )
    except Exception:
        text_message = (
            f"Habari {context['buyer_name']},\n\n"
            f"Mtu aliyekuwa ameshikilia mali "
            f"'{context['listing_title']}' anakaribia kumaliza "
            f"muda wake wa reservation.\n\n"
            f"Bofya kuweka reservation yako mapema:\n"
            f"{site_url}/dashboard/buyer/deals"
            f"?listing={context['listing_id']}&action=reserve\n\n"
            f"Asante,\nSokoMkononi"
        )

    try:
        send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[buyer.email],
            fail_silently=False,
        )
        logger.info(
            "[email] Waiting list expiring sent to %s (listing #%s)",
            buyer.email, listing.id,
        )
        return True
    except Exception:
        logger.exception(
            "Failed to send waiting-list email for listing %s",
            listing.id,
        )
        return False