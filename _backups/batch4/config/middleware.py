"""
DEPRECATED — the CSRF-bypass middleware was removed in the security
hardening pass. Cookie-based auth now correctly enforces CSRF; bearer
token auth is unaffected (CSRF only applies to cookie sessions).

This module is kept as a shim so `import config.middleware` does not
break for older code that still references it.
"""


class DisableCsrfForApiMiddleware:
    """No-op. Remove from MIDDLEWARE in settings.py."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)
