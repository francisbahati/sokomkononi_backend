import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import OTPVerification, PendingRegistration, User


class OTPThrottled(ValidationError):
    """Raised when a resend is attempted too soon."""


OTP_EXPIRY_MINUTES = 10
OTP_RESEND_SECONDS = 60
OTP_MAX_ATTEMPTS = 5

REGISTRATION = OTPVerification.VerificationType.EMAIL
PASSWORD_RESET = OTPVerification.VerificationType.PASSWORD_RESET_EMAIL


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_email(email):
    if not email:
        return None
    return email.strip().lower()


def normalize_tanzania_phone(phone):
    if not phone:
        return None

    phone = phone.strip().replace(" ", "").replace("-", "")

    if phone.startswith("+255"):
        return phone
    if phone.startswith("255"):
        return f"+{phone}"
    if phone.startswith("0"):
        return f"+255{phone[1:]}"

    raise ValidationError("Namba ya simu si sahihi. Tumia mfano 0712345678.")


# ============================================================
# OTP HELPERS
# ============================================================

def generate_otp():
    return str(secrets.randbelow(900000) + 100000)


def hash_otp(otp):
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def can_resend_otp(identifier, verification_type):
    latest = (
        OTPVerification.objects
        .filter(identifier=identifier, verification_type=verification_type)
        .order_by("-created_at")
        .first()
    )

    if not latest:
        return True

    elapsed = (timezone.now() - latest.created_at).total_seconds()
    return elapsed >= OTP_RESEND_SECONDS


def _create_otp_record(email, verification_type):
    identifier = normalize_email(email)

    if not can_resend_otp(identifier, verification_type):
        raise OTPThrottled({
            "detail": "Subiri sekunde 60 kabla ya kuomba OTP nyingine."
        })

    OTPVerification.objects.filter(
        identifier=identifier,
        verification_type=verification_type,
        is_used=False,
    ).update(is_used=True)

    otp = generate_otp()

    otp_record = OTPVerification.objects.create(
        identifier=identifier,
        verification_type=verification_type,
        otp_code=hash_otp(otp),
        expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES),
    )

    return otp_record, otp, identifier


def _check_otp(email, otp_code, verification_type):
    identifier = normalize_email(email)

    otp_record = (
        OTPVerification.objects
        .select_for_update()
        .filter(
            identifier=identifier,
            verification_type=verification_type,
            is_used=False,
        )
        .order_by("-created_at")
        .first()
    )

    if not otp_record:
        raise ValidationError({
            "otp_code": "OTP haipo au tayari imetumika."
        })

    if otp_record.is_expired:
        raise ValidationError({
            "otp_code": "OTP imekwisha muda wake. Omba OTP mpya."
        })

    if otp_record.attempts >= OTP_MAX_ATTEMPTS:
        raise ValidationError({
            "otp_code": "Umefikia idadi ya juu ya majaribio."
        })

    if not secrets.compare_digest(otp_record.otp_code, hash_otp(otp_code)):
        otp_record.attempts += 1
        otp_record.save(update_fields=["attempts"])
        remaining = OTP_MAX_ATTEMPTS - otp_record.attempts
        raise ValidationError({
            "otp_code": f"OTP si sahihi. Umebakiwa na {remaining} jaribio."
        })

    return otp_record


def _mark_otp_used(otp_record):
    otp_record.is_used = True
    otp_record.verified_at = timezone.now()
    otp_record.save(update_fields=["is_used", "verified_at"])


# ============================================================
# EMAIL
# ============================================================

def send_email_otp(email, otp):
    subject = "SokoMkononi - Nambari ya Uthibitisho"

    message = (
        "Habari,\n"
        "\n"
        "Karibu SokoMkononi \u2014 Mahali pa Kununua na Kuuza kwa Kujiamini.\n"
        "\n"
        "Ili kukamilisha usajili wa akaunti yako, tafadhali tumia nambari "
        "hii ya uthibitisho:\n"
        "\n"
        f"{otp}\n"
        "\n"
        "Nambari hii ni halali kwa dakika 10 pekee.\n"
        "\n"
        "Muhimu kwa usalama wako:\n"
        "Usimshirikishe mtu mwingine nambari hii. Timu ya SokoMkononi "
        "haitakuomba nambari yako ya uthibitisho kupitia simu, WhatsApp, "
        "SMS au njia nyingine yoyote.\n"
        "\n"
        "Ikiwa hukuomba nambari hii, unaweza kupuuza ujumbe huu.\n"
        "\n"
        "Asante kwa kuchagua SokoMkononi.\n"
        "\n"
        "SokoMkononi Team\n"
        "Mahali pa Kununua na Kuuza kwa Kujiamini."
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


def send_password_reset_email(email, otp):
    subject = "SokoMkononi - Kubadilisha Nenosiri"

    message = (
        "Habari,\n"
        "\n"
        "Tumepokea ombi la kubadilisha nenosiri la akaunti yako "
        "ya SokoMkononi.\n"
        "\n"
        "Nambari yako ya uthibitisho ni:\n"
        "\n"
        f"{otp}\n"
        "\n"
        "Nambari hii ni halali kwa dakika 10 pekee.\n"
        "\n"
        "Muhimu kwa usalama wako:\n"
        "Usimshirikishe mtu mwingine nambari hii. Timu ya SokoMkononi "
        "haitakuomba nambari yako ya uthibitisho kupitia simu, WhatsApp, "
        "SMS au njia nyingine yoyote.\n"
        "\n"
        "Ikiwa hukuomba kubadilisha nenosiri, puuza ujumbe huu \u2014 "
        "nenosiri lako halitabadilika.\n"
        "\n"
        "Asante kwa kuchagua SokoMkononi.\n"
        "\n"
        "SokoMkononi Team\n"
        "Mahali pa Kununua na Kuuza kwa Kujiamini."
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


# ============================================================
# REGISTRATION
# ============================================================

def create_pending_registration(data):
    email = normalize_email(data["email"])
    phone = normalize_tanzania_phone(data.get("phone"))

    if User.all_objects.filter(email__iexact=email).exists():
        raise ValidationError({
            "email": "Barua pepe hii tayari imesajiliwa."
        })

    if phone and User.objects.filter(phone=phone).exists():
        raise ValidationError({
            "phone": "Namba hii tayari imesajiliwa."
        })

    PendingRegistration.objects.filter(email__iexact=email).delete()

    if phone:
        PendingRegistration.objects.filter(phone=phone).delete()

    return PendingRegistration.objects.create(
        name=data["name"].strip(),
        email=email,
        phone=phone,
        account_type=data.get(
            "account_type", User.AccountType.INDIVIDUAL,
        ),
        password_hash=make_password(data["password"]),
    )


def send_registration_otp(pending):
    otp_record, otp, email = _create_otp_record(pending.email, REGISTRATION)

    try:
        from .tasks import send_email_otp_task
        send_email_otp_task.delay(email, otp)
    except Exception:
        otp_record.delete()
        raise

    return email


@transaction.atomic
def verify_registration_otp(identifier, otp_code):
    email = normalize_email(identifier)

    otp_record = _check_otp(email, otp_code, REGISTRATION)

    pending = (
        PendingRegistration.objects
        .select_for_update()
        .filter(email__iexact=email)
        .first()
    )

    if not pending:
        raise ValidationError({
            "detail": "Usajili unaosubiri haupatikani."
        })

    if User.all_objects.filter(email__iexact=pending.email).exists():
        raise ValidationError({"detail": "Barua pepe tayari imesajiliwa."})

    if pending.phone and User.objects.filter(phone=pending.phone).exists():
        raise ValidationError({
            "detail": "Namba ya simu tayari imesajiliwa."
        })

    user = User.objects.create(
        name=pending.name,
        email=pending.email,
        phone=pending.phone,
        account_type=pending.account_type,
        password=pending.password_hash,
        is_verified=True,
        is_active=True,
    )

    _mark_otp_used(otp_record)

    pending.delete()
    return user


# ============================================================
# PASSWORD RESET
# ============================================================

def send_password_reset_otp(user):
    if not user.email:
        raise ValidationError("Mtumiaji hana barua pepe.")

    otp_record, otp, email = _create_otp_record(user.email, PASSWORD_RESET)

    try:
        from .tasks import send_password_reset_email_task
        send_password_reset_email_task.delay(email, otp)
    except Exception:
        otp_record.delete()
        raise

    return email


@transaction.atomic
def verify_password_reset_otp(identifier, otp_code):
    email = normalize_email(identifier)

    otp_record = _check_otp(email, otp_code, PASSWORD_RESET)

    user = User.objects.filter(email__iexact=email).first()

    if not user:
        raise ValidationError({"detail": "Mtumiaji haipatikani."})

    _mark_otp_used(otp_record)

    return user


@transaction.atomic
def reset_user_password(user, new_password):
    if not user or user.is_deleted:
        raise ValidationError("Mtumiaji haipatikani.")
    if not new_password:
        raise ValidationError("Nenosiri jipya linahitajika.")

    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])

    _blacklist_user_refresh_tokens(user)
    return user


def _blacklist_user_refresh_tokens(user):
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )
    except ImportError:
        return

    outstanding = OutstandingToken.objects.filter(user=user)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=t) for t in outstanding],
        ignore_conflicts=True,
    )


# ============================================================
# ACCOUNT SOFT-DELETE / RESTORE
# ============================================================

@transaction.atomic
def delete_user_account(*, user, actor, reason=""):
    from apps.listings.models import Listing
    from apps.notifications.models import Notification

    if user.is_deleted:
        return user

    now = timezone.now()

    Listing.objects.filter(
        seller=user, is_deleted=False,
    ).update(
        is_deleted=True,
        deleted_at=now,
        deleted_by=actor,
        deletion_reason="Account deleted",
    )

    Notification.objects.filter(
        recipient=user, is_deleted=False,
    ).update(
        is_deleted=True,
        deleted_at=now,
        deleted_by=actor,
        deletion_reason="Account deleted",
    )

    user.delete(
        by=actor,
        reason=reason or "User requested deletion",
    )

    return user


@transaction.atomic
def restore_user_account(*, user, actor):
    from apps.listings.models import Listing
    from apps.notifications.models import Notification

    if not user.is_deleted:
        return user

    user.restore()

    Listing.objects.filter(
        seller=user,
        is_deleted=True,
        deletion_reason="Account deleted",
    ).update(
        is_deleted=False,
        deleted_at=None,
        deleted_by=None,
        deletion_reason="",
    )

    Notification.objects.filter(
        recipient=user,
        is_deleted=True,
        deletion_reason="Account deleted",
    ).update(
        is_deleted=False,
        deleted_at=None,
        deleted_by=None,
        deletion_reason="",
    )

    return user
