"""Liveness / readiness probe for container orchestration."""
from django.db import connection
from django.http import JsonResponse


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return JsonResponse(
            {"status": "unhealthy", "db": str(exc)},
            status=503,
        )
    return JsonResponse({"status": "ok"})
