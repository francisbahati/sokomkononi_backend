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
