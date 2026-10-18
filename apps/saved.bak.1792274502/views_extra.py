"""Extra views for the saved app — toggle + delete-by-listing."""
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.listings.models import Listing
from .models import SavedListing
from .serializers import SavedListingSerializer


def _saved_ids(user):
    return list(
        SavedListing.objects
        .filter(user=user, listing__is_deleted=False)
        .values_list("listing_id", flat=True)
    )


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def saved_toggle(request):
    listing_id = request.data.get("listing") or request.data.get("listing_id")
    if not listing_id:
        return Response(
            {"ok": False, "detail": "listing is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    listing = get_object_or_404(Listing, pk=listing_id, is_deleted=False)
    existing = SavedListing.objects.filter(user=request.user, listing=listing).first()
    if existing:
        existing.delete()
        return Response(
            {"ok": True, "saved": False, "listing_id": listing.id,
             "saved_ids": _saved_ids(request.user)},
            status=status.HTTP_200_OK,
        )
    saved = SavedListing.objects.create(
        user=request.user, listing=listing,
        snapshot_price=listing.price, snapshot_status=listing.status,
        snapshot_title=listing.title,
    )
    return Response(
        {"ok": True, "saved": True, "listing_id": listing.id,
         "saved_ids": _saved_ids(request.user),
         "data": SavedListingSerializer(saved, context={"request": request}).data},
        status=status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def saved_by_listing(request, listing_id):
    deleted, _ = SavedListing.objects.filter(
        user=request.user, listing_id=listing_id,
    ).delete()
    return Response(
        {"ok": True, "deleted": deleted, "saved_ids": _saved_ids(request.user)},
        status=status.HTTP_200_OK,
    )
