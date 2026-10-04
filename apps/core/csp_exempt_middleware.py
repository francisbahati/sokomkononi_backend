from csp.middleware import CSPMiddleware

EXEMPT_PREFIXES = ("/api/docs", "/api/schema", "/admin", "/swagger")


class CSPExemptMiddleware(CSPMiddleware):
    """
    Skips the CSP header for specific URL prefixes so that
    drf-spectacular's Swagger UI can initialize properly.
    """
    def process_response(self, request, response):
        # Skip CSP for exempted prefixes
        if any(request.path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return response
        return super().process_response(request, response)
