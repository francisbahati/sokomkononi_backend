"""Single source of truth for admin-action audit logging."""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def log_admin_action(*, request, action, target="", target_id=None,
                     details="", admin=None):
    """Log an admin action. Fails loud in production."""
    try:
        from apps.audit.services.audit import log_action
        return log_action(
            request=request, action=action, target=target,
            target_id=target_id, details=details, admin=admin,
        )
    except Exception:
        logger.exception("AUDIT LOG FAILURE: action=%s target=%s", action, target)
        if not settings.DEBUG:
            raise
