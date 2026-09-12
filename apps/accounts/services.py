import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    OTPVerification,
    PendingRegistration,
    User,
)


OTP_EXPIRY_MINUTES = 10
OTP_RESEND_SECONDS = 60
OTP_MAX_ATTEMPTS = 5


def normalize_email(email):
    if not email:
        return None

    return email.strip().lower()


def normalize_tanzania_phone(phone):
    """
    Converts common Tanzania formats into:

    +255712345678
    """

    if not phone:
        return None

    phone = (
        phone.strip()
        .replace(" ", "")
        .replace("-", "")
    )

    if phone.startswith("+255"):
        return phone

    if phone.startswith("255"):
        return f"+{phone}"

    if phone.startswith("0"):
        return f"+255{phone[1:]}"

    raise ValidationError(
        {
            "phone": (
                "Namba ya simu si sahihi. "
                "Tumia mfano 0712345678."
            )
        }
    )


def phone_for_nextsms(phone):
    """
    NextSMS examples use Tanzania numbers
    without the '+' prefix.
    """

    normalized = normalize_tanzania_phone(phone)

    return normalized.replace("+", "")


def generate_otp():
    return str(
        secrets.randbelow(900000) + 100000
    )


def hash_otp(otp):
    return hashlib.sha256(
        otp.encode("utf-8")
    ).hexdigest()


def send_email_otp(email, otp):
    subject = (
        "SokoMkononi - Nambari ya Uthibitishaji"
    )

    message = (
        "Habari,\n\n"
        "Nambari yako ya uthibitishaji wa "
        "SokoMkononi ni:\n\n"
        f"{otp}\n\n"
        f"Nambari hii itaisha baada ya "
        f"{OTP_EXPIRY_MINUTES} dakika.\n\n"
        "Usimpe mtu mwingine nambari hii.\n\n"
        "SokoMkononi"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


def send_sms_otp(phone, otp):
    """
    Send OTP through NextSMS API v2.

    Requires:

    PYNEXTSMS_TOKEN
    PYNEXTSMS_SENDER_ID
    """

    token = getattr(
        settings,
        "PYNEXTSMS_TOKEN",
        None,
    )

    sender_id = getattr(
        settings,
        "PYNEXTSMS_SENDER_ID",
        None,
    )

    if not token:
        raise RuntimeError(
            "PYNEXTSMS_TOKEN haijawekwa kwenye .env."
        )

    if not sender_id:
        raise RuntimeError(
            "PYNEXTSMS_SENDER_ID haijawekwa kwenye .env."
        )

    try:
        from pynextsms import SMSClient
    except ImportError as exc:
        raise RuntimeError(
            "pynextsms haijasakinishwa. "
            "Tumia: pip install pynextsms"
        ) from exc

    message = (
        "SokoMkononi: Nambari yako ya "
        f"uthibitishaji ni {otp}. "
        f"Itaisha baada ya "
        f"{OTP_EXPIRY_MINUTES} dakika."
    )

    nextsms_phone = phone_for_nextsms(phone)

    with SMSClient(
        token=token,
        sender_id=sender_id,
    ) as client:

        response = client.sms.send(
            nextsms_phone,
            message,
        )

    if hasattr(response, "successful"):
        if not response.successful:
            raise RuntimeError(
                f"NextSMS imeshindwa kutuma OTP: "
                f"{getattr(response, 'raw', response)}"
            )

    return response


def can_resend_otp(
    identifier,
    verification_type,
):
    latest = (
        OTPVerification.objects
        .filter(
            identifier=identifier,
            verification_type=verification_type,
        )
        .order_by("-created_at")
        .first()
    )

    if not latest:
        return True

    elapsed = (
        timezone.now() - latest.created_at
    ).total_seconds()

    return elapsed >= OTP_RESEND_SECONDS


def create_pending_registration(data):
    email = normalize_email(
        data.get("email")
    )

    phone = data.get("phone")

    if phone:
        phone = normalize_tanzania_phone(phone)

    if email and User.objects.filter(
        email__iexact=email
    ).exists():
        raise ValidationError(
            {
                "email": (
                    "Barua pepe hii tayari "
                    "imesajiliwa."
                )
            }
        )

    if phone and User.objects.filter(
        phone=phone
    ).exists():
        raise ValidationError(
            {
                "phone": (
                    "Namba hii tayari "
                    "imesajiliwa."
                )
            }
        )

    if email:
        PendingRegistration.objects.filter(
            email__iexact=email
        ).delete()

    if phone:
        PendingRegistration.objects.filter(
            phone=phone
        ).delete()

    pending = PendingRegistration.objects.create(
        name=data["name"].strip(),
        email=email,
        phone=phone,
        account_type=data.get(
            "account_type",
            User.AccountType.INDIVIDUAL,
        ),
        password_hash=make_password(
            data["password"]
        ),
    )

    return pending


def create_registration_otp(
    identifier,
    verification_type,
):
    identifier = identifier.strip()

    if verification_type == "EMAIL":
        identifier = normalize_email(
            identifier
        )

    elif verification_type == "PHONE":
        identifier = normalize_tanzania_phone(
            identifier
        )

    if not can_resend_otp(
        identifier,
        verification_type,
    ):
        raise ValidationError(
            {
                "detail": (
                    "Subiri sekunde 60 kabla ya "
                    "kuomba OTP nyingine."
                )
            }
        )

    OTPVerification.objects.filter(
        identifier=identifier,
        verification_type=verification_type,
        is_used=False,
    ).update(
        is_used=True
    )

    otp = generate_otp()

    otp_record = OTPVerification.objects.create(
        identifier=identifier,
        verification_type=verification_type,
        otp_code=hash_otp(otp),
        expires_at=(
            timezone.now()
            + timedelta(
                minutes=OTP_EXPIRY_MINUTES
            )
        ),
    )

    return otp_record, otp


def send_registration_otp(
    pending,
    verification_type,
):
    if verification_type == "EMAIL":

        if not pending.email:
            raise ValidationError(
                {
                    "email": (
                        "Usajili huu hauna "
                        "barua pepe."
                    )
                }
            )

        identifier = normalize_email(
            pending.email
        )

    elif verification_type == "PHONE":

        if not pending.phone:
            raise ValidationError(
                {
                    "phone": (
                        "Usajili huu hauna "
                        "namba ya simu."
                    )
                }
            )

        identifier = normalize_tanzania_phone(
            pending.phone
        )

    else:
        raise ValidationError(
            {
                "verification_type": (
                    "Aina ya uthibitishaji "
                    "si sahihi."
                )
            }
        )

    otp_record, otp = create_registration_otp(
        identifier=identifier,
        verification_type=verification_type,
    )

    try:

        if verification_type == "EMAIL":
            send_email_otp(
                identifier,
                otp,
            )

        else:
            send_sms_otp(
                identifier,
                otp,
            )

    except Exception:
        otp_record.delete()

        raise

    return identifier


@transaction.atomic
def verify_registration_otp(
    identifier,
    otp_code,
    verification_type,
):
    if verification_type == "EMAIL":
        identifier = normalize_email(
            identifier
        )

    elif verification_type == "PHONE":
        identifier = normalize_tanzania_phone(
            identifier
        )

    else:
        raise ValidationError(
            {
                "verification_type": (
                    "Aina ya uthibitishaji "
                    "si sahihi."
                )
            }
        )

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
        raise ValidationError(
            {
                "otp_code": (
                    "OTP haipo au tayari "
                    "imetumika."
                )
            }
        )

    if otp_record.is_expired:
        raise ValidationError(
            {
                "otp_code": (
                    "OTP imekwisha muda wake. "
                    "Omba OTP mpya."
                )
            }
        )

    if otp_record.attempts >= OTP_MAX_ATTEMPTS:
        raise ValidationError(
            {
                "otp_code": (
                    "Umefikia idadi ya juu "
                    "ya majaribio."
                )
            }
        )

    expected_hash = otp_record.otp_code
    supplied_hash = hash_otp(otp_code)

    if not secrets.compare_digest(
        expected_hash,
        supplied_hash,
    ):
        otp_record.attempts += 1
        otp_record.save(
            update_fields=["attempts"]
        )

        remaining = (
            OTP_MAX_ATTEMPTS
            - otp_record.attempts
        )

        raise ValidationError(
            {
                "otp_code": (
                    "OTP si sahihi. "
                    f"Umebakiwa na {remaining} "
                    "jaribio."
                )
            }
        )

    pending_query = PendingRegistration.objects

    if verification_type == "EMAIL":
        pending = (
            pending_query
            .filter(
                email__iexact=identifier
            )
            .first()
        )

    else:
        pending = (
            pending_query
            .filter(
                phone=identifier
            )
            .first()
        )

    if not pending:
        raise ValidationError(
            {
                "detail": (
                    "Usajili unaosubiri "
                    "haupatikani."
                )
            }
        )

    if pending.email and User.objects.filter(
        email__iexact=pending.email
    ).exists():
        raise ValidationError(
            {
                "detail": (
                    "Barua pepe tayari "
                    "imesajiliwa."
                )
            }
        )

    if pending.phone and User.objects.filter(
        phone=pending.phone
    ).exists():
        raise ValidationError(
            {
                "detail": (
                    "Namba ya simu tayari "
                    "imesajiliwa."
                )
            }
        )

    user = User.objects.create(
        name=pending.name,
        email=pending.email,
        phone=pending.phone,
        account_type=pending.account_type,
        password=pending.password_hash,
        is_verified=True,
        is_active=True,
    )

    otp_record.is_used = True
    otp_record.verified_at = timezone.now()

    otp_record.save(
        update_fields=[
            "is_used",
            "verified_at",
        ]
    )

    pending.delete()

    return user