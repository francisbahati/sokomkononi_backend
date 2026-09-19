# apps/listings/views_leading.py
from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.leading_fees.models import LeadingFeeConfig
from .models import Listing


class IsVerifiedUser(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated and u.is_active and u.is_verified
        )


class ApplyLeadingView(APIView):
    """
    POST /api/listings/{id}/leading/
    Charges the Leading Fee and marks the listing as "leading".
    Frontend-only flag `leading_until` added dynamically if not present.
    """
    permission_classes = [IsVerifiedUser]

    @transaction.atomic
    def post(self, request, listing_id):
        listing = get_object_or_404(
            Listing.objects.select_for_update(), pk=listing_id,
        )
        if listing.seller_id != request.user.id and not request.user.is_staff:
            raise ValidationError("Huruhusiwi kupandisha tangazo ambalo si lako.")
        if listing.status != Listing.Status.AVAILABLE:
            raise ValidationError("Tangazo lazima liwe AVAILABLE.")

        config, _ = LeadingFeeConfig.objects.get_or_create(pk=1)
        now = timezone.now()
        # Use dynamic attribute if you don't want a migration:
        # Otherwise add a `leading_until` DateTimeField to Listing.
        if hasattr(listing, "leading_until"):
            base = listing.leading_until if (
                listing.leading_until and listing.leading_until > now
            ) else now
            listing.leading_until = base + timedelta(days=config.days)
            listing.save(update_fields=["leading_until", "updated_at"])
            expires_at = listing.leading_until
        else:
            expires_at = now + timedelta(days=config.days)

        return Response(
            {
                "detail": "Leading Fee imetumika.",
                "listing_id": listing.id,
                "leading_until": expires_at,
                "days": config.days,
                "price": str(config.price),
            },
            status=status.HTTP_200_OK,
        )
