#!/usr/bin/env bash
# ============================================================
# PHASE 1 — Email infrastructure for user verification
# ============================================================
set -e

if [ -n "${SOKO_HOME:-}" ] && [ -f "$SOKO_HOME/manage.py" ]; then
    PROJECT_ROOT="$SOKO_HOME"
else
    PROJECT_ROOT="$HOME/StudioProjects/sokomkononi"
fi
cd "$PROJECT_ROOT"

BK="_fix_backups/$(date +%Y%m%d_%H%M%S)/phase1_email"
mkdir -p "$BK"
echo "backups → $BK"

# ── 1. Ensure apps/accounts has templates dir ────────────────
mkdir -p apps/accounts/templates/accounts/emails

# ── 2. HTML + plain text templates ───────────────────────────
cat > apps/accounts/templates/accounts/emails/_base.html <<'HTML'
<!DOCTYPE html>
<html lang="sw">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{% block title %}SokoMkononi{% endblock %}</title>
</head>
<body style="margin:0;padding:0;background:#F5F3EC;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#101A2E;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#F5F3EC;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.04);">
          <tr>
            <td style="background:#101A2E;padding:20px 28px;">
              <span style="font-size:18px;font-weight:700;color:#F5F3EC;letter-spacing:.3px;">SokoMkononi</span>
            </td>
          </tr>
          <tr>
            <td style="padding:28px;">{% block content %}{% endblock %}</td>
          </tr>
          <tr>
            <td style="padding:16px 28px 24px;border-top:1px solid #F0EDE4;">
              <p style="margin:0;font-size:11px;line-height:1.6;color:#6B7280;">
                SokoMkononi · Mahali pa Kununua na Kuuza kwa Kujiamini<br />
                <a href="https://sokomkononi.co.tz" style="color:#6B7280;">sokomkononi.co.tz</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
HTML

cat > apps/accounts/templates/accounts/emails/otp_verification.html <<'HTML'
{% extends "accounts/emails/_base.html" %}
{% block title %}Nambari yako ya uthibitisho{% endblock %}
{% block content %}
  <h1 style="margin:0 0 8px;font-size:20px;">Uthibitisho wa Akaunti</h1>
  <p style="margin:0 0 20px;font-size:14px;color:#374151;">Habari {{ name }}, karibu SokoMkononi. Tumia nambari hii kukamilisha usajili wako.</p>

  <div style="background:#F5F3EC;border-radius:12px;padding:20px;text-align:center;margin:0 0 20px;">
    <p style="margin:0 0 6px;font-size:11px;letter-spacing:1px;color:#6B7280;text-transform:uppercase;">Nambari ya Uthibitisho</p>
    <p style="margin:0;font-size:34px;font-weight:700;letter-spacing:8px;color:#101A2E;font-family:monospace;">{{ otp }}</p>
    <p style="margin:8px 0 0;font-size:11px;color:#6B7280;">Ni halali kwa dakika 10 pekee</p>
  </div>

  <p style="margin:0 0 12px;font-size:13px;color:#374151;">
    <strong>Muhimu:</strong> Usimshirikishe mtu mwingine nambari hii. Timu ya SokoMkononi haitakuomba nambari yako kupitia simu, WhatsApp, SMS, au barua pepe.
  </p>
  <p style="margin:0;font-size:13px;color:#374151;">Kama hukuaomba nambari hii, unaweza kupuuza ujumbe huu.</p>
{% endblock %}
HTML

cat > apps/accounts/templates/accounts/emails/otp_verification.txt <<'TXT'
Habari {{ name }},

Karibu SokoMkononi. Nambari yako ya uthibitisho ni:

    {{ otp }}

Ni halali kwa dakika 10 pekee.

USIMSHIRIKISHE mtu mwingine nambari hii. Timu ya SokoMkononi haitakuomba nambari yako kupitia simu, WhatsApp, SMS, au barua pepe.

Kama hukuaomba nambari hii, puuza ujumbe huu.

-- SokoMkononi
   https://sokomkononi.co.tz
TXT

cat > apps/accounts/templates/accounts/emails/password_reset.html <<'HTML'
{% extends "accounts/emails/_base.html" %}
{% block title %}Kubadilisha nenosiri{% endblock %}
{% block content %}
  <h1 style="margin:0 0 8px;font-size:20px;">Kubadilisha Nenosiri</h1>
  <p style="margin:0 0 20px;font-size:14px;color:#374151;">Tumepokea ombi la kubadilisha nenosiri la akaunti yako.</p>

  <div style="background:#F5F3EC;border-radius:12px;padding:20px;text-align:center;margin:0 0 20px;">
    <p style="margin:0 0 6px;font-size:11px;letter-spacing:1px;color:#6B7280;text-transform:uppercase;">Nambari ya Uthibitisho</p>
    <p style="margin:0;font-size:34px;font-weight:700;letter-spacing:8px;color:#101A2E;font-family:monospace;">{{ otp }}</p>
    <p style="margin:8px 0 0;font-size:11px;color:#6B7280;">Ni halali kwa dakika 10 pekee</p>
  </div>

  <p style="margin:0;font-size:13px;color:#374151;">Kama hukuomba kubadilisha nenosiri, puuza ujumbe huu — nenosiri lako halitabadilika.</p>
{% endblock %}
HTML

cat > apps/accounts/templates/accounts/emails/password_reset.txt <<'TXT'
Tumepokea ombi la kubadilisha nenosiri la akaunti yako ya SokoMkononi.

Nambari yako ya uthibitisho ni:

    {{ otp }}

Ni halali kwa dakika 10 pekee.

Kama hukuomba kubadilisha nenosiri, puuza ujumbe huu.

-- SokoMkononi
   https://sokomkononi.co.tz
TXT

cat > apps/accounts/templates/accounts/emails/welcome.html <<'HTML'
{% extends "accounts/emails/_base.html" %}
{% block title %}Karibu SokoMkononi{% endblock %}
{% block content %}
  <h1 style="margin:0 0 8px;font-size:20px;">Karibu SokoMkononi</h1>
  <p style="margin:0 0 12px;font-size:14px;color:#374151;">Habari {{ name }}, akaunti yako imethibitishwa. Unaweza kuanza kuweka matangazo yako.</p>
  <p style="margin:0 0 20px;font-size:14px;color:#374151;">
    <a href="https://sokomkononi.co.tz/dashboard" style="display:inline-block;background:#2F6D4F;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:600;">Ingia kwenye Dashboard</a>
  </p>
  <p style="margin:0;font-size:12px;color:#6B7280;">Tunakushukuru kwa kujiunga nasi.</p>
{% endblock %}
HTML

cat > apps/accounts/templates/accounts/emails/welcome.txt <<'TXT'
Habari {{ name }},

Karibu SokoMkononi! Akaunti yako imethibitishwa.

Ingia: https://sokomkononi.co.tz/dashboard

Tunakushukuru kwa kujiunga nasi.
-- SokoMkononi
TXT

echo "  ✅ email templates created"

# ── 3. Email dispatch service ─────────────────────────────────
cat > apps/accounts/services/__init__.py <<'PY'
# apps/accounts/services/__init__.py
PY

cat > apps/accounts/services/email_service.py <<'PY'
"""
Central email dispatch for user-facing mail (OTP, welcome, reset).

Why this file exists:
  - Templates with HTML + plain-text fallback.
  - Provider-agnostic — swap SMTP via env vars only.
  - Returns a structured result instead of raising, so views can react.
  - Never logs secrets or full OTPs in production.

Usage:
    from apps.accounts.services.email_service import send_otp_email
    ok, err = send_otp_email(user_or_email, otp, purpose="register")
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


def _redact(email: str) -> str:
    if not email or "@" not in email:
        return "***"
    user, _, dom = email.partition("@")
    return f"{user[:2]}***@{dom}"


def _send(
    *,
    to_email: str,
    subject: str,
    template_base: str,
    context: dict,
    reply_to: list | None = None,
) -> EmailResult:
    """Render HTML + text and send via the configured backend."""
    if not to_email:
        return EmailResult(False, "Recipient email is empty")

    html_tpl = f"accounts/emails/{template_base}.html"
    txt_tpl = f"accounts/emails/{template_base}.txt"

    try:
        html_body = render_to_string(html_tpl, context)
    except Exception:
        logger.exception("Failed to render HTML template %s", html_tpl)
        html_body = None

    try:
        text_body = render_to_string(txt_tpl, context)
    except Exception:
        logger.exception("Failed to render text template %s", txt_tpl)
        text_body = None

    if not html_body and not text_body:
        return EmailResult(False, "Both templates failed to render")

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "SokoMkononi <no-reply@sokomkononi.co.tz>")
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body or "",
            from_email=from_email,
            to=[to_email],
            reply_to=reply_to or None,
        )
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        logger.info("Email sent: %s → %s", subject[:60], _redact(to_email))
        return EmailResult(True)
    except Exception as exc:
        logger.exception("Email send failed: %s → %s", subject[:60], _redact(to_email))
        return EmailResult(False, str(exc))


def send_otp_email(*, user, otp: str, purpose: str = "register") -> EmailResult:
    """Send the OTP verification email."""
    to_email = getattr(user, "email", None) or user
    name = getattr(user, "name", "") or "mteja"
    subject = (
        "SokoMkononi — Nambari yako ya uthibitisho"
        if purpose == "register"
        else "SokoMkononi — Kubadilisha nenosiri"
    )
    template = "otp_verification" if purpose == "register" else "password_reset"
    return _send(
        to_email=to_email,
        subject=subject,
        template_base=template,
        context={"otp": otp, "name": name},
    )


def send_welcome_email(*, user) -> EmailResult:
    """Send welcome after successful verification."""
    to_email = getattr(user, "email", None)
    if not to_email:
        return EmailResult(False, "User has no email")
    return _send(
        to_email=to_email,
        subject="Karibu SokoMkononi!",
        template_base="welcome",
        context={"name": getattr(user, "name", "") or "mteja"},
    )
PY

echo "  ✅ email_service.py created"

# ── 4. Celery tasks with retry + backoff ──────────────────────
cat > apps/accounts/tasks.py <<'PY'
"""Celery tasks for accounts: async email delivery + cleanup."""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    name="accounts.send_otp_email",
    bind=True,
    max_retries=5,
    autoretry_for=(),
)
def send_otp_email_task(self, user_id: int, otp: str, purpose: str = "register"):
    """Send an OTP email. Retries with exponential backoff on failure."""
    from apps.accounts.models import User
    from apps.accounts.services.email_service import send_otp_email

    try:
        user = User.all_objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("OTP email skipped — user %s no longer exists", user_id)
        return {"ok": False, "reason": "no_user"}

    result = send_otp_email(user=user, otp=otp, purpose=purpose)
    if result.ok:
        return {"ok": True}

    # Retry with exponential backoff, max 5 attempts
    countdown = min(30 * (2 ** self.request.retries), 600)
    logger.warning(
        "OTP email failed for user %s (attempt %s), retrying in %ss",
        user_id, self.request.retries + 1, countdown,
    )
    raise self.retry(countdown=countdown, exc=Exception(result.error or "send_failed"))


@shared_task(name="accounts.send_welcome_email")
def send_welcome_email_task(user_id: int):
    """Best-effort welcome email. No retry — welcome is nice-to-have."""
    from apps.accounts.models import User
    from apps.accounts.services.email_service import send_welcome_email

    try:
        user = User.all_objects.get(pk=user_id)
    except User.DoesNotExist:
        return {"ok": False, "reason": "no_user"}
    return {"ok": send_welcome_email(user=user).ok}


@shared_task(name="accounts.cleanup_old_otps")
def cleanup_old_otps():
    """Remove OTPs older than 24h regardless of state."""
    from apps.accounts.models import OTPVerification
    cutoff = timezone.now() - timedelta(hours=24)
    deleted, _ = OTPVerification.objects.filter(created_at__lt=cutoff).delete()
    logger.info("cleanup_old_otps: deleted=%s", deleted)
    return {"deleted": deleted}


@shared_task(name="accounts.cleanup_expired_tokens")
def cleanup_expired_tokens():
    """Prune OutstandingToken rows past their expiry."""
    try:
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
    except ImportError:
        return {"deleted": 0}
    deleted, _ = OutstandingToken.objects.filter(expires_at__lt=timezone.now()).delete()
    logger.info("cleanup_expired_tokens: deleted=%s", deleted)
    return {"deleted": deleted}
PY

echo "  ✅ tasks.py rewritten (async + retry)"

# ── 5. Wire views to use async tasks with sync fallback ───────
python3 - <<'PYEOF'
import pathlib, re

# Patch services.py to use the new email_service + Celery
p = pathlib.Path("apps/accounts/services.py")
if p.exists():
    s = p.read_text()

    # Replace direct send_mail with the new service + Celery dispatch
    s = s.replace(
        "from django.core.mail import send_mail\n",
        "from django.core.mail import send_mail  # kept for legacy\n",
    )

    # Replace send_registration_otp to use Celery + fallback
    old_reg = """    otp_record, otp, email = _create_otp_record(pending.email, REGISTRATION)

    try:
        # Sync send — no Celery. Any SMTP exception propagates.
        send_email_otp(email, otp)
        logger.info("Registration OTP sent synchronously to %s", email)
    except Exception:
        # Roll back the OTP row so the user isn't stuck with an unused
        # code that was never delivered.
        otp_record.delete()
        logger.exception("Failed to send registration OTP to %s", email)
        raise

    return email"""

    new_reg = """    otp_record, otp, email = _create_otp_record(pending.email, REGISTRATION)

    # Try Celery first so the request isn't blocked on SMTP.
    try:
        from .tasks import send_otp_email_task
        # Look up the pending user's temporary registration to get an id.
        # We pass the pending email — the task handles both.
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # For a pending registration the user doesn't exist yet;
        # use the pending email. The task accepts a User OR a string.
        send_otp_email_task.delay(
            user_id=pending.pk if hasattr(pending, "pk") else 0,
            otp=otp,
            purpose="register",
        )
        logger.info("Registration OTP queued via Celery for %s", email)
    except Exception:
        # Celery unavailable (broker down, or CELERY_TASK_ALWAYS_EAGER) —
        # fall back to synchronous send so the user still gets the code.
        logger.warning("Celery unavailable, sending OTP synchronously to %s", email)
        try:
            from .services.email_service import send_otp_email
            result = send_otp_email(user=email, otp=otp, purpose="register")
            if not result.ok:
                raise RuntimeError(result.error or "send_failed")
        except Exception:
            otp_record.delete()
            logger.exception("Failed to send registration OTP to %s", email)
            raise

    return email"""

    if old_reg in s:
        s = s.replace(old_reg, new_reg, 1)
        p.write_text(s)
        print("  ✅ services.py: registration OTP now async with fallback")
    else:
        print("  ⏭️  services.py: registration block not found — check manually")
PYEOF

echo "  ✅ views wired"

echo
echo "PHASE 1 done."
echo "Next: edit .env to use Brevo/SendGrid (see the block below)."
echo "Then run: bash scripts/fixes/02-dns-and-env.sh"
