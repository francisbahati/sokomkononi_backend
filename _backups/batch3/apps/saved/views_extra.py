"""Extra views for the saved app — toggle + delete-by-listing."""
from django.shortcuts import get_object_or_404

from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.listings.models import Listing

from .models import SavedListing


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def saved_toggle(request):
    """POST /api/saved/toggle/  body: {"listing": <id>}"""
    listing_id = request.data.get("listing")
    if not listing_id:
        return Response(
            {"detail": "listing is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    listing = get_object_or_404(Listing, pk=listing_id)

    existing = SavedListing.objects.filter(
        user=request.user, listing=listing,
    ).first()

    if existing:
        existing.delete()
        return Response({"saved": False}, status=status.HTTP_200_OK)

    SavedListing.objects.create(
        user=request.user,
        listing=listing,
        snapshot_price=listing.price,
        snapshot_status=listing.status,
        snapshot_title=listing.title,
    )
    return Response({"saved": True}, status=status.HTTP_200_OK)


@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def saved_by_listing(request, listing_id):
    """DELETE /api/saved/listing/<id>/"""
    SavedListing.objects.filter(
        user=request.user, listing_id=listing_id,
    ).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
