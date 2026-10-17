"""Liveness + deep readiness."""
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone


def health(request):
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
            c.fetchone()
    except Exception as exc:
        return JsonResponse({"status": "unhealthy", "db": str(exc)}, status=503)
    return JsonResponse({"status": "ok", "time": timezone.now().isoformat()})


def health_deep(request):
    out = {"status": "ok"}
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
            c.fetchone()
        out["database"] = "ok"
    except Exception as exc:
        out["database"] = str(exc)
        out["status"] = "degraded"
    try:
        cache.set("__health__", "1", 5)
        out["redis"] = "ok" if cache.get("__health__") == "1" else "read_failed"
    except Exception as exc:
        out["redis"] = str(exc)
        out["status"] = "degraded"
    return JsonResponse(out, status=200 if out["status"] == "ok" else 503)
