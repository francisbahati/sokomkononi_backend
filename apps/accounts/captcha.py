import logging
import requests
from django.conf import settings
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_captcha(token, ip=None):
    secret = getattr(settings, "TURNSTILE_SECRET_KEY", "")
    if not secret:
        return  # imezimwa, sawa na frontend isiyo na site key

    if not token:
        raise ValidationError({"detail": "Thibitisha kuwa wewe si roboti."})

    data = {"secret": secret, "response": token}
    if ip:
        data["remoteip"] = ip
    try:
        ok = requests.post(VERIFY_URL, data=data, timeout=5).json().get("success") is True
    except (requests.RequestException, ValueError):
        logger.exception("Turnstile verify failed")
        raise ValidationError({"detail": "Imeshindwa kuthibitisha captcha. Jaribu tena."})

    if not ok:
        raise ValidationError({"detail": "Captcha imeshindwa. Jaribu tena."})