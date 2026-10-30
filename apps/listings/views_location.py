"""
Listing location + multipart image handling.

Endpoints:
    PATCH /api/listings/{id}/location/    update lat/lng
    POST  /api/listings/                  (multipart with images)
    POST  /api/listings/{id}/images/bulk/ bulk image upload
"""
import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.parsers import (
    FormParser, JSONParser, MultiPartParser,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.image_utils import validate_image, MAX_LISTING_IMAGE_BYTES

from .models import Listing, ListingImage
from .permissions import IsOwnerOrAdmin, IsVerifiedUser
from .serializers import (
    ListingDetailSerializer,
)
from .serializers_location import (
    ListingCreateWithImagesSerializer,
    LocationUpdateSerializer,
)

logger = logging.getLogger(__name__)


# ============================================================
# PATCH /api/listings/{id}/location/
# ============================================================
class ListingLocationUpdateView(APIView):
    """
    Update only the location fields of a listing.
    """
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def patch(self, request, pk=None):
        listing = get_object_or_404(Listing, pk=pk)
        self.check_object_permissions(request, listing)

        # Lock the row
        with transaction.atomic():
            listing = Listing.objects.select_for_update().get(pk=listing.pk)

            serializer = LocationUpdateSerializer(
                listing, data=request.data, partial=True,
            )
            serializer.is_valid(raise_exception=True)
            d = serializer.validated_data

            updates = []

            if "latitude" in d:
                listing.latitude = d["latitude"]
                updates.append("latitude")
            if "longitude" in d:
                listing.longitude = d["longitude"]
                updates.append("longitude")
            if "location" in d:
                listing.location = (d["location"] or "").strip() or listing.location
                updates.append("location")
            if "address_text" in d:
                listing.address_text = (d["address_text"] or "").strip()
                updates.append("address_text")

            if updates:
                listing.location_updated_at = timezone.now()
                updates.append("location_updated_at")
                updates.append("updated_at")
                listing.save(update_fields=updates)

        # Log
        try:
            from apps.core.audit import log_admin_action
            # ✅ Tumia details={"sw","en"}
            log_admin_action(
                request=request,
                action="listing.location_updated",
                target="Listing",
                target_id=listing.id,
                details={
                    "sw": f"Eneo la tangazo limebadilishwa: lat={listing.latitude} lng={listing.longitude}",
                    "en": f"Listing location updated: lat={listing.latitude} lng={listing.longitude}",
                },
            )
        except Exception:
            logger.exception("audit log failed for location update")

        return Response(
            ListingDetailSerializer(
                listing, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


# ============================================================
# POST /api/listings/{id}/images/bulk/
# ============================================================
class ListingImagesBulkUploadView(APIView):
    """
    Upload multiple images at once.
    """
    permission_classes = [
        permissions.IsAuthenticated,
        IsVerifiedUser,
        IsOwnerOrAdmin,
    ]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, listing_id=None):
        listing = get_object_or_404(Listing, pk=listing_id)
        self.check_object_permissions(request, listing)

        files = request.FILES.getlist("images") or request.FILES.getlist("images[]")
        if not files:
            return Response(
                {"detail": "Hakuna picha zilizopokelewa (field: 'images')."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(files) > 10:
            return Response(
                {"detail": "Unaweza kupakia picha 10 kwa wakati mmoja."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate each image first
        for f in files:
            ok, err = validate_image(
                f, max_bytes=MAX_LISTING_IMAGE_BYTES, field="images",
            )
            if not ok:
                return Response(
                    {"detail": f"{f.name}: {err}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        created = []
        with transaction.atomic():
            # Lock and determine if listing already has a primary
            listing = Listing.objects.select_for_update().get(pk=listing.pk)
            has_primary = ListingImage.objects.filter(
                listing=listing, is_primary=True,
            ).exists()

            for idx, f in enumerate(files):
                should_be_primary = (not has_primary and idx == 0)
                if should_be_primary:
                    ListingImage.objects.filter(
                        listing=listing, is_primary=True,
                    ).update(is_primary=False)

                img = ListingImage.objects.create(
                    listing=listing,
                    image=f,
                    is_primary=should_be_primary,
                    ordering=idx,
                )
                created.append(img)
                if should_be_primary:
                    has_primary = True

        from .serializers import ListingImageSerializer
        return Response(
            {
                "count": len(created),
                "images": ListingImageSerializer(
                    created, many=True, context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# POST /api/listings/ (multipart variant)
# ============================================================
class ListingCreateWithImagesView(APIView):
    """
    Create a listing + images in a single multipart request.
    """
    permission_classes = [permissions.IsAuthenticated, IsVerifiedUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = ListingCreateWithImagesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        files = request.FILES.getlist("images") or request.FILES.getlist("images[]")

        # Validate images before touching the DB
        if len(files) > ListingCreateWithImagesSerializer.MAX_IMAGES:
            return Response(
                {"detail": "Picha zisizidi 10."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for f in files:
            ok, err = validate_image(
                f, max_bytes=MAX_LISTING_IMAGE_BYTES, field="images",
            )
            if not ok:
                return Response(
                    {"detail": f"{f.name}: {err}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            listing = Listing.objects.create(
                seller=request.user,
                category=d["category"],
                title=d["title"],
                description=d["description"],
                price=d["price"],
                location=d["location"],
                latitude=d.get("latitude"),
                longitude=d.get("longitude"),
                address_text=d.get("address_text", ""),
                attributes=d.get("attributes", {}),
                status=Listing.Status.DRAFT,
            )

            # Create fee record
            try:
                from .services.listing_fee import create_listing_fee
                create_listing_fee(listing)
                listing.status = Listing.Status.PENDING_PAYMENT
                listing.save(update_fields=["status", "updated_at"])
            except Exception:
                logger.exception("Fee computation failed for listing %s", listing.pk)

            # Attach images
            for idx, f in enumerate(files):
                ListingImage.objects.create(
                    listing=listing,
                    image=f,
                    is_primary=(idx == 0),
                    ordering=idx,
                )

        # Build response (with payment block)
        data = ListingDetailSerializer(
            listing, context={"request": request},
        ).data

        fee = getattr(listing, "listing_fee", None)
        if fee is not None:
            data["payment"] = {
                "required": True,
                "amount": str(fee.amount),
                "amount_display": f"TZS {fee.amount:,.0f}",
                "currency": "TZS",
                "status": fee.payment_status,
                "listing_id": listing.id,
                "pay_endpoint": f"/api/listings/{listing.id}/fee/pay/",
            }
        else:
            data["payment"] = {
                "required": False,
                "amount": None,
                "amount_display": None,
                "currency": "TZS",
                "status": "NOT_CONFIGURED",
                "listing_id": listing.id,
                "pay_endpoint": f"/api/listings/{listing.id}/fee/pay/",
            }

        return Response(data, status=status.HTTP_201_CREATED)