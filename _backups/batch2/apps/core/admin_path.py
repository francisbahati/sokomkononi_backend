"""
Shared helper: get the admin dashboard path prefix.

Notification action_urls that point to admin screens must use this
so the SPA can deep-link into the admin app regardless of where it's
mounted.
"""
from django.conf import settings


def _admin_path():
    """Local alias for the shared admin-path helper."""
    from apps.core.admin_path import get_admin_path
    return get_admin_path()



def get_admin_path() -> str:
    """Return the admin dashboard path prefix (no trailing slash)."""
    path = getattr(settings, "ADMIN_PATH", "/smk-control-9x7k") or "/smk-control-9x7k"
    # Ensure leading slash and no trailing slash
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/")
