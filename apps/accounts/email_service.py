"""
Central email dispatch. Templates + plain-text fallback + structured result.
Swap providers via env vars only.
"""
import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    ok: bool
    error: str = ""


def _redact(email):
    if not email or "@" not in email:
        return "***"
    u, _, d = email.partition("@")
    return f"{u[:2]}***@{d}"


def _send(*, to_email, subject, template_base, context):
    if not to_email:
        return EmailResult(False, "recipient empty")

    try:
        html_body = render_to_string(f"accounts/emails/{template_base}.html", context)
    except Exception:
        logger.exception("HTML render failed: %s", template_base)
        html_body = None

    try:
        text_body = render_to_string(f"accounts/emails/{template_base}.txt", context)
    except Exception:
        logger.exception("TXT render failed: %s", template_base)
        text_body = None

    if not html_body and not text_body:
        return EmailResult(False, "both templates failed to render")

    from_email = getattr(
        settings, "DEFAULT_FROM_EMAIL",
        "SokoMkononi <no-reply@sokomkononi.co.tz>",
    )
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body or "",
            from_email=from_email,
            to=[to_email],
        )
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        logger.info("Email sent: %s -> %s", subject[:60], _redact(to_email))
        return EmailResult(True)
    except Exception as exc:
        logger.exception("Email send failed: %s -> %s", subject[:60], _redact(to_email))
        return EmailResult(False, str(exc))


def send_otp_email(*, user, otp, purpose="register"):
    to_email = getattr(user, "email", None) or user
    name = getattr(user, "name", "") or "mteja"
    if purpose == "register":
        subject = "SokoMkononi — Nambari yako ya uthibitisho"
        template = "otp_verification"
    else:
        subject = "SokoMkononi — Kubadilisha nenosiri"
        template = "password_reset"
    return _send(
        to_email=to_email, subject=subject,
        template_base=template, context={"otp": otp, "name": name},
    )


def send_welcome_email(*, user):
    """
    Send the welcome email.

    `user` can be a User instance, a dict with {email, name}, or a
    plain email string. This lets tests and scripts call it easily.
    """
    if isinstance(user, str):
        to_email = user
        name = "mteja"
    elif isinstance(user, dict):
        to_email = user.get("email") or user.get("EMAIL")
        name = user.get("name") or user.get("NAME") or "mteja"
    else:
        to_email = getattr(user, "email", None)
        name = getattr(user, "name", "") or "mteja"

    if not to_email:
        return EmailResult(False, "no email")

    return _send(
        to_email=to_email,
        subject="Karibu SokoMkononi!",
        template_base="welcome",
        context={"name": name},
    )

def send_account_deleted_email(*, to_email, name="mteja", reason=""):
    """
    Send account-deleted notification.
    Called BEFORE the user record is hard-deleted, so the email
    address is still valid at this point.
    """
    if not to_email:
        return EmailResult(False, "no email")

    return _send(
        to_email=to_email,
        subject="SokoMkononi — Akaunti yako imefutwa",
        template_base="account_deleted",
        context={
            "name": name or "mteja",
            "reason": reason or "—",
        },
    )


def send_account_suspended_email(*, to_email, name="mteja", reason=""):
    """Send account-suspended notification."""
    if not to_email:
        return EmailResult(False, "no email")

    return _send(
        to_email=to_email,
        subject="SokoMkononi — Akaunti yako imesimamishwa",
        template_base="account_suspended",
        context={
            "name": name or "mteja",
            "reason": reason or "—",
        },
    )

def send_verification_approved_email(
    *, to_email, name="mteja", verification_type="", action_url=""
):
    """
    Send verification approved notification.

    Called by apps/verifications/notify.py after admin approves.
    """
    if not to_email:
        return EmailResult(False, "no email")

    type_label = {
        "SELLER": "Muuzaji",
        "BUYER": "Mnunuzi",
    }.get(verification_type, verification_type or "—")

    return _send(
        to_email=to_email,
        subject="SokoMkononi — Uthibitisho wako umeidhinishwa",
        template_base="verification_approved",
        context={
            "name": name or "mteja",
            "verification_type": type_label,
            "action_url": action_url or "/dashboard/verification",
        },
    )


def send_verification_rejected_email(
    *, to_email, name="mteja", verification_type="", reason="", action_url=""
):
    """
    Send verification rejected notification.

    Called by apps/verifications/notify.py after admin rejects.
    """
    if not to_email:
        return EmailResult(False, "no email")

    type_label = {
        "SELLER": "Muuzaji",
        "BUYER": "Mnunuzi",
    }.get(verification_type, verification_type or "—")

    return _send(
        to_email=to_email,
        subject="SokoMkononi — Uthibitisho umekataliwa",
        template_base="verification_rejected",
        context={
            "name": name or "mteja",
            "verification_type": type_label,
            "reason": reason or "—",
            "action_url": action_url or "/dashboard/verification",
        },
    )

def send_documents_requested_email(
    *, to_email, name="mteja", message="", action_url=""
):
    """
    Send email when admin requests more documents.

    Called by apps/verifications/notify.py.
    """
    if not to_email:
        return EmailResult(False, "no email")

    return _send(
        to_email=to_email,
        subject="SokoMkononi — Nyaraka zaidi zinahitajika",
        template_base="verification_documents_requested",
        context={
            "name": name or "mteja",
            "message": message or "Tafadhali pakia nyaraka zaidi.",
            "action_url": action_url or "/dashboard/verification",
        },
    )