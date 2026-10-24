"""Uniform DRF error envelope + friendly throttle + bilingual details."""
import re
from django.db.models import ProtectedError
from django.utils import translation
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_handler


# ============================================================
# UJUMBE WA LUGHA MBILI (SW / EN)
# ============================================================
_LANG_MESSAGES = {
    "permission_denied": {
        "sw": "Huna ruhusa ya kufanya kitendo hiki.",
        "en": "You don't have permission to perform this action.",
    },
    "not_authenticated": {
        "sw": "Tafadhali ingia kwenye akaunti yako kwanza.",
        "en": "Please log in to your account first.",
    },
    "authentication_failed": {
        "sw": "Uthibitisho wa akaunti umeshindikana. Ingia tena.",
        "en": "Authentication failed. Please log in again.",
    },
    "not_found": {
        "sw": "Kitu ulichokitafuta hakipo.",
        "en": "The requested resource was not found.",
    },
    "method_not_allowed": {
        "sw": "Njia hii ya ombi hairuhusiwi kwenye sehemu hii.",
        "en": "This request method is not allowed on this endpoint.",
    },
    "validation_error": {
        "sw": "Taarifa ulizoweka haziko sahihi. Tafadhali kagua.",
        "en": "The information you provided is invalid. Please check.",
    },
    "protected_error": {
        "sw": "Haifutiki — inatumika mahali pengine.",
        "en": "Cannot delete — it is used elsewhere.",
    },
    "throttled": {
        "sw": "Umetuma maombi mengi kwa muda mfupi. Tafadhali subiri {wait} kisha ujaribu tena. Asante kwa uvumilivu.",
        "en": "You've made too many requests in a short time. Please wait {wait} and try again. Thank you for your patience.",
    },
    "server_error": {
        "sw": "Hitilafu imetokea kwenye mfumo. Tafadhali jaribu tena baadaye.",
        "en": "An error occurred on the server. Please try again later.",
    },
}


def _humanize_wait(seconds: int, lang: str = "sw") -> str:
    seconds = max(0, int(seconds or 0))
    if seconds < 60:
        return f"{seconds} sekunde" if lang == "sw" else f"{seconds} seconds"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        if lang == "sw":
            return f"dakika {minutes}" + (f" na sekunde {secs}" if secs else "")
        return (
            f"{minutes} minute" + ("s" if minutes != 1 else "")
            + (f" and {secs} seconds" if secs else "")
        )
    hours, mins = divmod(minutes, 60)
    if lang == "sw":
        return f"saa {hours}" + (f" na dakika {mins}" if mins else "")
    return (
        f"{hours} hour" + ("s" if hours != 1 else "")
        + (f" and {mins} minutes" if mins else "")
    )


def _get_lang(request) -> str:
    """Chukua lugha kutoka: query (?lang=), Accept-Language, au default 'sw'."""
    lang = "sw"
    try:
        if request is not None:
            q_lang = (request.query_params.get("lang") or "").lower()
            if q_lang in ("en", "sw"):
                return q_lang
            accept = (request.META.get("HTTP_ACCEPT_LANGUAGE") or "").lower()
            if accept.startswith("en"):
                return "en"
    except Exception:
        pass
    return lang


def _throttled_response(exc: Throttled, request):
    lang = _get_lang(request)
    retry_after = None
    try:
        retry_after = int(getattr(exc, "wait", None) or 0) or None
    except (TypeError, ValueError):
        retry_after = None

    if not retry_after:
        detail_str = str(exc.detail) if hasattr(exc, "detail") else ""
        m = re.search(r"(\d+)\s*second", detail_str)
        if m:
            retry_after = int(m.group(1))

    wait_text = (
        _humanize_wait(retry_after or 0, lang)
        if retry_after
        else ("muda mfupi" if lang == "sw" else "a short while")
    )
    message = _LANG_MESSAGES["throttled"][lang].format(wait=wait_text)

    body = {
        "error": {
            "code": "THROTTLED",
            "message": message,
            "retry_after": retry_after,
            "language": lang,
        }
    }
    response = Response(body, status=status.HTTP_429_TOO_MANY_REQUESTS)
    if retry_after:
        response["Retry-After"] = str(retry_after)
    return response


def _protected_response(exc: ProtectedError, request):
    lang = _get_lang(request)
    return Response(
        {
            "error": {
                "code": "PROTECTED_ERROR",
                "message": _LANG_MESSAGES["protected_error"][lang],
                "message_sw": _LANG_MESSAGES["protected_error"]["sw"],
                "message_en": _LANG_MESSAGES["protected_error"]["en"],
                "protected_objects": [str(o) for o in exc.protected_objects][:10],
                "language": lang,
            }
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _translate_known_exception(exc, lang: str) -> tuple[str, str] | None:
    """Rudisha (code, message) kwa exceptions zinazojulikana."""
    if isinstance(exc, PermissionDenied):
        return "PERMISSION_DENIED", _LANG_MESSAGES["permission_denied"][lang]
    if isinstance(exc, NotAuthenticated):
        return "NOT_AUTHENTICATED", _LANG_MESSAGES["not_authenticated"][lang]
    if isinstance(exc, AuthenticationFailed):
        return "AUTHENTICATION_FAILED", _LANG_MESSAGES["authentication_failed"][lang]
    if isinstance(exc, NotFound):
        return "NOT_FOUND", _LANG_MESSAGES["not_found"][lang]
    if isinstance(exc, MethodNotAllowed):
        return "METHOD_NOT_ALLOWED", _LANG_MESSAGES["method_not_allowed"][lang]
    if isinstance(exc, ValidationError):
        return "VALIDATION_ERROR", _LANG_MESSAGES["validation_error"][lang]
    return None


def handler(exc, context):
    request = context.get("request")
    lang = _get_lang(request)
    rid = getattr(request, "request_id", None) if request else None

    # ── Throttle ─────────────────────────────────────────────
    if isinstance(exc, Throttled):
        return _throttled_response(exc, request)

    # ── ProtectedError ───────────────────────────────────────
    if isinstance(exc, ProtectedError):
        return _protected_response(exc, request)

    # ── Exceptions zinazojulikana ────────────────────────────
    known = _translate_known_exception(exc, lang)
    if known:
        code, message = known
        body = {
            "error": {
                "code": code,
                "message": message,
                "language": lang,
            }
        }
        # ValidationError: weka undani halisi ili frontend iweze kuonyesha sababu.
        #   - detail ni dict  -> error.fields  = {field: [ujumbe, ...]}
        #   - detail ni list  -> error.details = [ujumbe, ...]
        #     (ValidationError("maandishi") ina detail ya aina ya list; awali ujumbe huu ulipotea
        #      kabisa na mteja alipata ujumbe wa jumla tu.)
        if isinstance(exc, ValidationError):
            detail = exc.detail
            if isinstance(detail, dict):
                body["error"]["fields"] = {
                    k: (v if isinstance(v, list) else [v]) for k, v in detail.items()
                }
            else:
                items = detail if isinstance(detail, list) else [detail]
                body["error"]["details"] = [str(i) for i in items]
        if rid:
            body["error"]["request_id"] = rid
        return Response(body, status=exc.status_code)

    # ── DRF default ─────────────────────────────────────────
    resp = drf_handler(exc, context)
    if resp is None:
        return None

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
    env["language"] = lang
    resp.data = {"error": env}
    return resp