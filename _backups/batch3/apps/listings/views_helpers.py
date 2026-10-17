"""
Helpers for listing endpoints.

Ensures URL kwargs that should be integers return a clean JSON 400
instead of Django's HTML 404 when the client sends a bad ID
(e.g. a frontend-local id like "l_1790106344646").
"""
from rest_framework import status
from rest_framework.response import Response


def require_int_listing_id(listing_id):
    """
    Returns (int_id, None) on success.
    Returns (None, Response) on failure.
    """
    if isinstance(listing_id, int):
        return listing_id, None

    try:
        return int(listing_id), None
    except (TypeError, ValueError):
        return None, Response(
            {
                "detail": (
                    f"Listing ID si sahihi: '{listing_id}'. "
                    "Tumia ID ya namba iliyotolewa na backend."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
