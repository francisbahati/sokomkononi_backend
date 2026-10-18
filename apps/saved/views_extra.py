"""Extra views for the saved app — toggle + delete-by-listing.

Both return a fresh `saved_ids` array plus `ok: true` so the frontend
can update the heart icon and saved-list without a full page reload.
The list includes soft-deleted listings so the frontend can render
"removed" snapshot cards for listings the user saved before deletion.
"""
from django.shortcuts import get_object_or_404

from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.listings.models import Listing

from .models import SavedListing
from .serializers import SavedListingSerializer


def _saved_ids(user):
    """All saved listing IDs for the user — INCLUDING soft-deleted."""
    return list(
        SavedListing.objects
        .filter(user=user)
        .values_list("listing_id", flat=True)
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def saved_toggle(request):
    """POST /api/saved/toggle/  body: {"listing": <id>}"""
    raw = request.data.get("listing") or request.data.get("listing_id")
    if raw in (None, ""):
        return Response(
            {"ok": False, "detail": "listing is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        listing_id = int(raw)
    except (TypeError, ValueError):
        return Response(
            {"ok": False, "detail": "listing must be an integer"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check for existing save FIRST — allows unsaving deleted listings.
    existing = SavedListing.objects.filter(
        user=request.user, listing_id=listing_id,
    ).first()

    if existing:
        existing.delete()
        return Response(
            {
                "ok": True,
                "saved": False,
                "listing_id": listing_id,
                "saved_ids": _saved_ids(request.user),
            },
            status=status.HTTP_200_OK,
        )

    # Not saved yet — the listing must exist and not be deleted.
    listing = get_object_or_404(
        Listing, pk=listing_id, is_deleted=False,
    )

    saved = SavedListing.objects.create(
        user=request.user,
        listing=listing,
        snapshot_price=listing.price,
        snapshot_status=listing.status,
        snapshot_title=listing.title,
    )
    return Response(
        {
            "ok": True,
            "saved": True,
            "listing_id": listing.id,
            "saved_ids": _saved_ids(request.user),
            "data": SavedListingSerializer(
                saved, context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def saved_by_listing(request, listing_id):
    """DELETE /api/saved/listing/<id>/"""
    deleted, _ = SavedListing.objects.filter(
        user=request.user, listing_id=listing_id,
    ).delete()
    return Response(
        {
            "ok": True,
            "deleted": deleted,
            "saved_ids": _saved_ids(request.user),
        },
        status=status.HTTP_200_OK,
    )
