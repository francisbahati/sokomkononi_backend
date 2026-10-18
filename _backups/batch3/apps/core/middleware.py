"""Request-id middleware."""
import uuid


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.request_id = rid
        response = self.get_response(request)
        response["X-Request-ID"] = rid
        return response
