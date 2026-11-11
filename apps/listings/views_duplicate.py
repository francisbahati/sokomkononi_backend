# apps/listings/views_duplicate.py
from datetime import timedelta

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.listings.models import Listing


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def check_duplicate_listing(request):
    """
    POST /api/listings/check-duplicate/
    Body: { title, price, location, category, window_days }
    Returns { is_duplicate: bool, existing: {...} | null }
    """
    title = (request.data.get("title") or "").strip()
    location = (request.data.get("location") or "").strip()
    price = request.data.get("price")
    category = request.data.get("category")  # ✅ MPYA
    try:
        window_days = int(request.data.get("window_days") or 30)
    except (TypeError, ValueError):
        window_days = 30

    if not title:
        return Response({"is_duplicate": False, "existing": None})

    cutoff = timezone.now() - timedelta(days=window_days)
    qs = (
        Listing.objects
        .filter(
            seller=request.user,
            title__iexact=title,
            created_at__gte=cutoff,
        )
        .exclude(status__in=["REJECTED", "ARCHIVED"])
    )

    # ✅ Chuja kwa category (muhimu ili listings za categories tofauti
    # zisionekane kama duplicate)
    if category:
        if isinstance(category, str) and not category.isdigit():
            qs = qs.filter(category__slug=category)
        else:
            qs = qs.filter(category_id=category)

    if location:
        qs = qs.filter(location__iexact=location)

    if price is not None:
        try:
            qs = qs.filter(price=float(price))
        except (TypeError, ValueError):
            pass

    match = qs.first()
    if not match:
        return Response({"is_duplicate": False, "existing": None})

    return Response({
        "is_duplicate": True,
        "existing": {
            "id": match.id,
            "title": match.title,
            "price": str(match.price),
            "location": match.location or "",
            "status": match.status,
            "category": match.category.slug if match.category else None,
        },
    })