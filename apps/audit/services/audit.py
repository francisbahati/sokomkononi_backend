"""
Helper used throughout the codebase to log admin actions.

    from apps.audit.services.audit import log_action
    log_action(
        request=request,
        action="listing.approved",
        target="Listing",
        target_id=listing.id,
        details=f"Approved: {listing.title}",
    )
"""

from ..models import AuditLog


def log_action(*, request, action, target="", target_id=None, details="", admin=None):
    user = admin or getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None

    return AuditLog.objects.create(
        action=action,
        admin_user=user,
        admin_name=getattr(user, "name", "") or "",
        target=target or "",
        target_id=target_id,
        details=details or "",
    )