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


def log_action(*, request, action, target="", target_id=None,
               details="", admin=None):
    user = admin or getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    meta = getattr(request, "META", {}) if request else {}
    return AuditLog.objects.create(
        action=action,
        admin_user=user,
        admin_name=getattr(user, "name", "") or "",
        target=target or "",
        target_id=target_id,
        details=details or "",
        ip_address=_client_ip(request),
        user_agent=(meta.get("HTTP_USER_AGENT", "") or "")[:255],
        request_path=(getattr(request, "path", "") or "")[:500],
        request_method=(getattr(request, "method", "") or "")[:10],
    )
