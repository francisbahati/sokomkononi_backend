# apps/verifications/notify.py

import logging

from django.conf import settings
from django.db import transaction as db_transaction
from django.utils.translation import gettext as _, override

from apps.notifications.models import Notification
from apps.notifications.services.notification import create_notification

logger = logging.getLogger(__name__)


# ============================================================
# URL HELPER — huzalisha URL KAMILI kwa email
# ============================================================
def _absolute_url(path):
    """
    Badilisha relative path kuwa URL kamili.
    "/dashboard/verification" -> "https://sokomkononi.co.tz/dashboard/verification"
    """
    if not path:
        path = "/dashboard/verification"
    if path.startswith(("http://", "https://")):
        return path
    base = getattr(settings, "SITE_URL", "https://sokomkononi.co.tz")
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


# ============================================================
# USER HELPERS — guards ili kuepuka AttributeError
# ============================================================
def _user_lang(r):
    """
    Rudisha lugha ya mtumiaji kutoka UserPreferences.

    Fallback: 'sw' kama:
      - user hayupo (amefutwa)
      - preferences haipo (haijaundwa)
      - language haipo/tupu
    """
    user = getattr(r, "user", None)
    if not user:
        return "sw"
    prefs = getattr(user, "preferences", None)
    if prefs is None:
        return "sw"
    return getattr(prefs, "language", None) or "sw"


def _user_email(r):
    """Rudisha email ya mtumiaji au ya ombi (fallback)."""
    user = getattr(r, "user", None)
    email = getattr(user, "email", None) if user else None
    return email or getattr(r, "user_email", "") or ""


def _user_name(r):
    """Rudisha jina la mtumiaji au la ombi (fallback)."""
    user = getattr(r, "user", None)
    name = getattr(user, "name", None) if user else None
    return name or getattr(r, "user_name", "") or _("mteja")


def _recipient(r):
    """Rudisha recipient kwa create_notification — None kama user hayupo."""
    return getattr(r, "user", None)


# ============================================================
# APPROVED
# ============================================================
def notify_approved(r):
    """
    Tuma notification + email kwa mtumiaji baada ya verification ku-approve.
    """
    lang = _user_lang(r)
    recipient = _recipient(r)

    def _notif():
        if not recipient:
            logger.warning(
                "[verifications.notify] notify_approved: no user for %s", r.id,
            )
            return
        try:
            with override(lang):
                create_notification(
                    recipient=recipient,
                    notification_type=Notification.NotificationType.ACCOUNT_VERIFIED,
                    title=_("Uthibitisho wako umeidhinishwa"),
                    message=_(
                        "Ombi lako la kuthibitishwa kuwa {type} limeidhinishwa. "
                        "Sasa unaweza kufanya biashara kwa uhuru."
                    ).format(type=r.type),
                    priority=Notification.Priority.HIGH,
                    related_object_type="verification",
                    related_object_id=r.id,
                    action_url="/dashboard/verification",
                )
        except Exception:
            logger.exception("notify_approved (notification) %s", r.id)

    def _email():
        try:
            from apps.accounts.email_service import (
                send_verification_approved_email,
            )
            send_verification_approved_email(
                to_email=_user_email(r),
                name=_user_name(r),
                verification_type=r.type,
                action_url=_absolute_url("/dashboard/verification"),
                language=lang,
            )
        except Exception:
            logger.exception("notify_approved (email) %s", r.id)

    db_transaction.on_commit(_notif)
    db_transaction.on_commit(_email)


# ============================================================
# REJECTED
# ============================================================
def notify_rejected(r, reason=""):
    """
    Tuma notification + email kwa mtumiaji baada ya verification ku-reject.
    """
    lang = _user_lang(r)
    recipient = _recipient(r)

    def _notif():
        if not recipient:
            logger.warning(
                "[verifications.notify] notify_rejected: no user for %s", r.id,
            )
            return
        try:
            with override(lang):
                create_notification(
                    recipient=recipient,
                    notification_type=Notification.NotificationType.GENERAL,
                    title=_("Uthibitisho umekataliwa"),
                    message=_(
                        "Ombi lako la kuthibitishwa kuwa {type} "
                        "limekataliwa. Sababu: {reason}"
                    ).format(type=r.type, reason=reason or _("hakuna sababu")),
                    priority=Notification.Priority.HIGH,
                    related_object_type="verification",
                    related_object_id=r.id,
                    action_url="/dashboard/verification",
                )
        except Exception:
            logger.exception("notify_rejected (notification) %s", r.id)

    def _email():
        try:
            from apps.accounts.email_service import (
                send_verification_rejected_email,
            )
            send_verification_rejected_email(
                to_email=_user_email(r),
                name=_user_name(r),
                verification_type=r.type,
                reason=reason,
                action_url=_absolute_url("/dashboard/verification"),
                language=lang,
            )
        except Exception:
            logger.exception("notify_rejected (email) %s", r.id)

    db_transaction.on_commit(_notif)
    db_transaction.on_commit(_email)


# ============================================================
# DOCUMENTS REQUESTED
# ============================================================
def notify_documents_requested(r, message=""):
    """
    Tuma notification + email kwa mtumiaji kuhusu documents zaidi.

    Kumbuka: `message` inatoka kwa admin (free text). Hii HAITAFSIRIWI
    kwa sababu ni ujumbe wa binadamu. Template (title + fallback body)
    ndiyo inayotafsiriwa.
    """
    lang = _user_lang(r)
    recipient = _recipient(r)
    message = (message or "").strip()

    def _notif():
        if not recipient:
            logger.warning(
                "[verifications.notify] notify_documents_requested: "
                "no user for %s", r.id,
            )
            return
        try:
            with override(lang):
                create_notification(
                    recipient=recipient,
                    notification_type=Notification.NotificationType.GENERAL,
                    title=_("Nyaraka zaidi zinahitajika"),
                    message=message or _("Tafadhali pakia nyaraka zaidi."),
                    priority=Notification.Priority.HIGH,
                    related_object_type="verification",
                    related_object_id=r.id,
                    action_url="/dashboard/verification",
                )
        except Exception:
            logger.exception(
                "notify_documents_requested (notification) %s", r.id,
            )

    def _email():
        try:
            from apps.accounts.email_service import (
                send_documents_requested_email,
            )
            # Kama message ni tupu, tumia fallback iliyotafsiriwa
            with override(lang):
                body = message or _("Tafadhali pakia nyaraka zaidi.")
            send_documents_requested_email(
                to_email=_user_email(r),
                name=_user_name(r),
                message=body,
                action_url=_absolute_url("/dashboard/verification"),
                language=lang,
            )
        except Exception:
            logger.exception(
                "notify_documents_requested (email) %s", r.id,
            )

    db_transaction.on_commit(_notif)
    db_transaction.on_commit(_email)