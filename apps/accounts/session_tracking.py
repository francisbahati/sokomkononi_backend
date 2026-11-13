"""
UserSession tracking — inaunda/inasasisha safu ya UserSession kila token inapotolewa.

Kabla ya hii hakuna popote kwenye views kilichokuwa kinaunda UserSession, kwa hiyo
orodha ya vifaa kwenye Profile ilikuwa tupu. Kila kazi hapa HAIVUNJI login ikishindwa
(inaandika log tu).
"""
import logging

from django.utils import timezone

from .models import UserSession

logger = logging.getLogger(__name__)

MAX_SESSIONS_PER_USER = 30


def _client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def _device_name(ua):
    ua = (ua or "").lower()
    if not ua:
        return "Kifaa kisichojulikana"
    if "edg/" in ua:
        browser = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "chrome" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua:
        browser = "Safari"
    else:
        browser = "Kivinjari"
    if "android" in ua:
        os_name = "Android"
    elif "iphone" in ua or "ipad" in ua or "ios" in ua:
        os_name = "iOS"
    elif "windows" in ua:
        os_name = "Windows"
    elif "mac os" in ua or "macintosh" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
    else:
        os_name = ""
    return f"{browser} · {os_name}" if os_name else browser


def record_session(request, refresh, user):
    """Iite baada ya `RefreshToken.for_user(user)` (login, verify-otp, 2fa, social).
    `user` lazima ipitishwe waziwazi: wakati wa login request.user bado ni anonymous."""
    try:
        ua = (request.META.get("HTTP_USER_AGENT") or "")[:500]
        UserSession.objects.update_or_create(
            refresh_jti=str(refresh["jti"]),
            defaults={
                "user_id": user.pk,
                "device_name": _device_name(ua)[:200],
                "ip_address": _client_ip(request),
                "user_agent": ua,
            },
        )
        # Usiache safu zikue bila mwisho
        stale = list(
            UserSession.objects.filter(user_id=user.pk)
            .order_by("-last_seen")
            .values_list("pk", flat=True)[MAX_SESSIONS_PER_USER:]
        )
        if stale:
            UserSession.objects.filter(pk__in=stale).delete()
    except Exception:
        logger.exception("record_session failed")


def rotate_session(old_jti, new_jti):
    """Refresh rotation inabadilisha jti — safu ifuate token mpya."""
    try:
        UserSession.objects.filter(refresh_jti=old_jti).update(
            refresh_jti=new_jti, last_seen=timezone.now(),
        )
    except Exception:
        logger.exception("rotate_session failed")


def drop_session(jti):
    """Iite wakati wa logout."""
    try:
        UserSession.objects.filter(refresh_jti=jti).delete()
    except Exception:
        logger.exception("drop_session failed")