"""Helper used throughout the codebase to log admin actions."""
import ipaddress
import logging

from django.conf import settings

from ..models import AuditLog

logger = logging.getLogger(__name__)


def _client_ip(request):
    """Only trust XFF if REMOTE_ADDR is a trusted proxy."""
    trusted = getattr(settings, "TRUSTED_PROXY_CIDRS", [])
    meta = getattr(request, "META", {}) if request else {}
    remote = meta.get("REMOTE_ADDR", "")

    if trusted and remote:
        try:
            remote_ip = ipaddress.ip_address(remote)
            is_trusted = any(
                remote_ip in ipaddress.ip_network(cidr, strict=False)
                for cidr in trusted
            )
        except ValueError:
            is_trusted = False

        if is_trusted:
            xff = meta.get("HTTP_X_FORWARDED_FOR", "")
            if xff:
                return xff.split(",")[0].strip()

    return remote or None


def _split_details(details, details_sw, details_en):
    """
    `details` inaweza kuwa:
      - str                      -> logs za zamani (lugha moja)
      - {"sw": "...", "en": ...} -> logs mpya (lugha mbili)
    Inarudisha (legacy, sw, en). `legacy` daima ina kitu (sw -> en -> str ya zamani)
    ili utafutaji na clients za zamani ziendelee kufanya kazi.
    """
    if isinstance(details, dict):
        details_sw = details_sw or details.get("sw") or ""
        details_en = details_en or details.get("en") or ""
        details = ""
    details = details or ""
    details_sw = details_sw or ""
    details_en = details_en or ""
    legacy = details or details_sw or details_en
    return legacy, details_sw, details_en


def log_action(*, request, action, target="", target_id=None,
               details="", details_sw="", details_en="", admin=None):
    user = admin or getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    meta = getattr(request, "META", {}) if request else {}
    legacy, d_sw, d_en = _split_details(details, details_sw, details_en)
    return AuditLog.objects.create(
        action=action,
        admin_user=user,
        admin_name=getattr(user, "name", "") or "",
        target=target or "",
        target_id=target_id,
        details=legacy,
        details_sw=d_sw,
        details_en=d_en,
        ip_address=_client_ip(request),
        user_agent=(meta.get("HTTP_USER_AGENT", "") or "")[:255],
        request_path=(getattr(request, "path", "") or "")[:500],
        request_method=(getattr(request, "method", "") or "")[:10],
    )