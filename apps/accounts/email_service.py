# apps/accounts/email_service.py

"""
Central email dispatch. Templates + plain-text fallback + structured result.
Swap providers via env vars only.
"""
import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.translation import gettext as _, override

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


# ============================================================
# URL HELPER
# ============================================================
def _absolute_url(path, default_path="/dashboard/verification"):
    path = path or default_path
    if path.startswith(("http://", "https://")):
        return path
    base = getattr(settings, "SITE_URL", "https://sokomkononi.co.tz")
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


# ============================================================
# SEND HELPER — inaunga mkono lugha
# ============================================================
def _send(*, to_email, subject, template_base, context, language="sw"):
    if not to_email:
        return EmailResult(False, "recipient empty")

    lang = language or "sw"

    with override(lang):
        html_body = None
        try:
            html_body = render_to_string(
                f"accounts/emails/{template_base}.html", context,
            )
        except Exception:
            logger.exception("HTML render failed: %s", template_base)

        text_body = None
        try:
            text_body = render_to_string(
                f"accounts/emails/{template_base}.txt", context,
            )
        except Exception:
            logger.exception("TXT render failed: %s", template_base)

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
        logger.exception(
            "Email send failed: %s -> %s", subject[:60], _redact(to_email),
        )
        return EmailResult(False, str(exc))


# ============================================================
# OTP + welcome + account
# ============================================================
def send_otp_email(*, user, otp, purpose="register"):
    to_email = getattr(user, "email", None) or user
    name = getattr(user, "name", "") or _("mteja")
    if purpose == "register":
        subject = _("SokoMkononi — Nambari yako ya uthibitisho")
        template = "otp_verification"
    else:
        subject = _("SokoMkononi — Kubadilisha nenosiri")
        template = "password_reset"
    return _send(
        to_email=to_email, subject=str(subject),
        template_base=template, context={"otp": otp, "name": name},
    )


def send_welcome_email(*, user):
    if isinstance(user, str):
        to_email = user
        name = _("mteja")
    elif isinstance(user, dict):
        to_email = user.get("email") or user.get("EMAIL")
        name = user.get("name") or user.get("NAME") or _("mteja")
    else:
        to_email = getattr(user, "email", None)
        name = getattr(user, "name", "") or _("mteja")

    if not to_email:
        return EmailResult(False, "no email")

    return _send(
        to_email=to_email,
        subject=str(_("Karibu SokoMkononi!")),
        template_base="welcome",
        context={"name": name},
    )


def send_account_deleted_email(*, to_email, name="mteja", reason=""):
    if not to_email:
        return EmailResult(False, "no email")

    return _send(
        to_email=to_email,
        subject=str(_("SokoMkononi — Akaunti yako imefutwa")),
        template_base="account_deleted",
        context={
            "name": name or _("mteja"),
            "reason": reason or "—",
        },
    )


def send_account_suspended_email(*, to_email, name="mteja", reason=""):
    if not to_email:
        return EmailResult(False, "no email")

    return _send(
        to_email=to_email,
        subject=str(_("SokoMkononi — Akaunti yako imesimamishwa")),
        template_base="account_suspended",
        context={
            "name": name or _("mteja"),
            "reason": reason or "—",
        },
    )


# ============================================================
# VERIFICATION EMAILS — bilingual
# ============================================================
def send_verification_approved_email(
    *, to_email, name="mteja", verification_type="", action_url="",
    language="sw",
):
    if not to_email:
        return EmailResult(False, "no email")

    lang = language or "sw"
    action_url = _absolute_url(action_url, "/dashboard/verification")

    with override(lang):
        type_label = {
            "SELLER": _("Muuzaji"),
            "BUYER": _("Mnunuzi"),
        }.get(verification_type, verification_type or "—")

        subject = _("SokoMkononi — Uthibitisho wako umeidhinishwa")

    return _send(
        to_email=to_email,
        subject=str(subject),
        template_base="verification_approved",
        context={
            "name": name or _("mteja"),
            "verification_type": type_label,
            "action_url": action_url,
            "language": lang,
        },
        language=lang,
    )


def send_verification_rejected_email(
    *, to_email, name="mteja", verification_type="", reason="",
    action_url="", language="sw",
):
    if not to_email:
        return EmailResult(False, "no email")

    lang = language or "sw"
    action_url = _absolute_url(action_url, "/dashboard/verification")

    with override(lang):
        type_label = {
            "SELLER": _("Muuzaji"),
            "BUYER": _("Mnunuzi"),
        }.get(verification_type, verification_type or "—")

        subject = _("SokoMkononi — Uthibitisho umekataliwa")

    return _send(
        to_email=to_email,
        subject=str(subject),
        template_base="verification_rejected",
        context={
            "name": name or _("mteja"),
            "verification_type": type_label,
            "reason": reason or "—",
            "action_url": action_url,
            "language": lang,
        },
        language=lang,
    )


def send_documents_requested_email(
    *, to_email, name="mteja", message="", action_url="", language="sw",
):
    if not to_email:
        return EmailResult(False, "no email")

    lang = language or "sw"
    action_url = _absolute_url(action_url, "/dashboard/verification")

    with override(lang):
        subject = _("SokoMkononi — Nyaraka zaidi zinahitajika")
        body = message or _("Tafadhali pakia nyaraka zaidi.")

    return _send(
        to_email=to_email,
        subject=str(subject),
        template_base="verification_documents_requested",
        context={
            "name": name or _("mteja"),
            "message": body,
            "action_url": action_url,
            "language": lang,
        },
        language=lang,
    )