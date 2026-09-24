# apps/listings/views_leading.py
"""
Leading Fee endpoint.

    POST /api/listings/{id}/leading/
    Body: { payment_reference: "LF-..." }
"""
from datetime import timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions
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
    permission_classes = [IsVerifiedUser]

    @transaction.atomic
    def post(self, request, listing_id):
        listing = get_object_or_404(
            Listing.objects.select_for_update(), pk=listing_id,
        )

        if listing.seller_id != request.user.id and not request.user.is_staff:
            raise ValidationError(
                "Huruhusiwi kupandisha tangazo ambalo si lako."
            )
        if listing.status != Listing.Status.AVAILABLE:
            raise ValidationError("Tangazo lazima liwe AVAILABLE.")

        payment_reference = (request.data or {}).get("payment_reference", "")
        payment_reference = (payment_reference or "").strip()
        if not payment_reference:
            raise ValidationError(
                {"payment_reference": "Payment reference inahitajika."}
            )

        config, _ = LeadingFeeConfig.objects.get_or_create(pk=1)
        now = timezone.now()

        current = getattr(listing, "leading_until", None)
        base = current if (current and current > now) else now

        listing.leading_until = base + timedelta(days=config.days)
        listing.save(update_fields=["leading_until", "updated_at"])

        return Response(
            {
                "detail": "Leading Fee imetumika.",
                "listing_id": listing.id,
                "leading_until": listing.leading_until,
                "days": config.days,
                "price": str(config.price),
                "payment_reference": payment_reference,
            },
        )
