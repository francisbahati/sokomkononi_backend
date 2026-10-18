# apps/core/exceptions.py
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler


def handler(exc, context):
    if isinstance(exc, ProtectedError):
        return Response(
            {
                "error": {
                    "code": "PROTECTED_ERROR",
                    "message": "Haifutiki — inatumika mahali pengine.",
                    "protected_objects": [str(o) for o in exc.protected_objects][:10],
                }
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    resp = drf_handler(exc, context)
    if resp is None:
        return None

    request = context.get("request")
    rid = getattr(request, "request_id", None)

    body = resp.data
    if isinstance(body, dict) and "error" in body and isinstance(body["error"], dict):
        return resp

    if isinstance(body, dict) and "detail" in body:
        env = {"code": exc.__class__.__name__.upper(), "message": str(body["detail"])}
    elif isinstance(body, dict):
        field = next(iter(body.keys()), None)
        val = body[field]
        msg = str(val[0]) if isinstance(val, list) and val else str(val)
        env = {"code": "VALIDATION_ERROR", "message": msg}
        if field:
            env["field"] = field
    else:
        env = {"code": "ERROR", "message": str(body)}

    if rid:
        env["request_id"] = rid
    resp.data = {"error": env}
    return resp