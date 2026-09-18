from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from apps.listings.models import Listing

from .models import SavedListing
from .serializers import (
    SavedListingCreateSerializer,
    SavedListingSerializer,
)


class SavedListingViewSet(viewsets.GenericViewSet):
    """
    Buyer's saved / favorite listings.

        GET     /api/saved/                list mine
        POST    /api/saved/                add { listing: <id> }
        DELETE  /api/saved/{id}/           remove
        DELETE  /api/saved/listing/{lid}/  remove by listing id
        POST    /api/saved/toggle/         toggle { listing: <id> }
    """

    serializer_class = SavedListingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            SavedListing.objects
            .filter(user=self.request.user)
            .select_related("listing", "listing__category")
            .prefetch_related("listing__images")
        )

    def list(self, request):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        serializer = SavedListingSerializer(
            page if page is not None else queryset,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        request=SavedListingCreateSerializer,
        responses={201: SavedListingSerializer},
    )
    def create(self, request):
        serializer = SavedListingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = serializer.validated_data["listing"]

        saved, created = SavedListing.objects.get_or_create(
            user=request.user,
            listing=listing,
            defaults={
                "snapshot_price": listing.price,
                "snapshot_status": listing.status,
                "snapshot_title": listing.title,
            },
        )

        output = SavedListingSerializer(saved, context={"request": request})
        return Response(
            output.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def destroy(self, request, pk=None):
        instance = self.get_queryset().filter(pk=pk).first()
        if not instance:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        instance.delete()
        return Response(
            {"detail": "Imeondolewa kwenye zilizohifadhiwa."},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["delete"],
        url_path=r"listing/(?P<listing_id>\d+)",
    )
    def remove_by_listing(self, request, listing_id=None):
        qs = self.get_queryset().filter(listing_id=listing_id)
        if not qs.exists():
            return Response(
                {"detail": "Haipo kwenye zilizohifadhiwa."},
                status=status.HTTP_404_NOT_FOUND,
            )
        qs.delete()
        return Response(
            {"detail": "Imeondolewa kwenye zilizohifadhiwa."},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=SavedListingCreateSerializer,
        responses={200: None, 201: SavedListingSerializer},
    )
    @action(detail=False, methods=["post"], url_path="toggle")
    def toggle(self, request):
        serializer = SavedListingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = serializer.validated_data["listing"]

        existing = SavedListing.objects.filter(
            user=request.user,
            listing=listing,
        ).first()

        if existing:
            existing.delete()
            return Response(
                {"saved": False, "listing_id": listing.id},
                status=status.HTTP_200_OK,
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
                "saved": True,
                "data": SavedListingSerializer(
                    saved, context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )