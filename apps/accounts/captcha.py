import logging

import requests
from django.conf import settings
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Header ambayo App (Android/iOS) itatuma kwenye kila request.
# Web haitumi — kwa hiyo web inaendelea kuhitaji captcha.
MOBILE_CLIENT_HEADER = "HTTP_X_CLIENT"
MOBILE_CLIENT_VALUE = "mobile-app"


def is_mobile_client(request):
    """Return True kama request inatoka kwenye App yetu (Android/iOS)."""
    return request.META.get(MOBILE_CLIENT_HEADER) == MOBILE_CLIENT_VALUE


def verify_captcha(token, ip=None, *, is_mobile_app=False):
    secret = getattr(settings, "TURNSTILE_SECRET_KEY", "")
    if not secret:
        return  # imezimwa, sawa na frontend isiyo na site key

    # App yetu haitumii Turnstile widget; tunaiachia ipite.
    # Web (browser) inaendelea kuhitaji token.
    if is_mobile_app:
        logger.info("Turnstile skipped for mobile app (ip=%s)", ip)
        return

    if not token:
        raise ValidationError({"detail": "Thibitisha kuwa wewe si roboti."})

    data = {"secret": secret, "response": token}
    if ip:
        data["remoteip"] = ip
    try:
        ok = (
            requests.post(VERIFY_URL, data=data, timeout=5)
            .json()
            .get("success")
            is True
        )
    except (requests.RequestException, ValueError):
        logger.exception("Turnstile verify failed")
        raise ValidationError(
            {"detail": "Imeshindwa kuthibitisha captcha. Jaribu tena."}
        )

    if not ok:
        raise ValidationError({"detail": "Captcha imeshindwa. Jaribu tena."})