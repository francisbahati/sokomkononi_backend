"""
SokoMkononi middleware.

DisableCsrfForApiMiddleware
----------------------------
Ensures Django's CsrfViewMiddleware never enforces CSRF on API paths.

Why this exists:
    The SokoMkononi API is authenticated exclusively with JWT Bearer
    tokens. CSRF is a cookie-based attack vector and is irrelevant to
    a token-authenticated API. This middleware guarantees no cookie —
    stale sessionid, csrftoken, injected by an extension, or set by a
    previous backend config — can trigger a 403 on /api/*.

Scope:
    Applies only to paths beginning with `/api/`.
    Django admin (`/django-admin/`), the browsable API, and any
    non-API Django view keep their normal CSRF enforcement.
"""
import logging

logger = logging.getLogger(__name__)


class DisableCsrfForApiMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        if path.startswith("/api/"):
            # Django's CsrfViewMiddleware.process_view() bails out
            # immediately when this flag is set on the request.
            request._dont_enforce_csrf_checks = True
        return self.get_response(request)
