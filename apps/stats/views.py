"""
Public stats endpoint — inarudisha idadi ya users, properties, na rating.

GET /api/stats/public/  (AllowAny)

Cache ya sekunde 60 ili database isileme kwa kila mtu anayefungua homepage.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Avg
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


STATS_CACHE_KEY = "sokomkononi:public_stats:v1"
STATS_CACHE_TTL = 60  # sekunde


class PublicStatsView(APIView):
    """
    GET /api/stats/public/

    Response:
        {
            "users": 140,
            "properties": 11,
            "rating": 4.7
        }
    """
    permission_classes = [AllowAny]

    def get(self, request):
        cached = cache.get(STATS_CACHE_KEY)
        if cached is not None:
            return Response(cached)

        User = get_user_model()

        # ── Users (bila admin, bila waliofutwa) ──────────────
        try:
            users_count = User.objects.filter(
                is_staff=False,
                is_deleted=False,
            ).count()
        except Exception:
            users_count = User.objects.filter(is_staff=False).count()

        # ── Properties (live listings pekee) ────────────────
        try:
            from apps.listings.models import Listing
            properties_count = Listing.objects.filter(
                is_deleted=False,
                status=Listing.Status.LIVE,
            ).count()
        except Exception:
            properties_count = 0

        # ── Rating (kutoka reviews/feedback kama ipo) ───────
        rating = 4.7
        try:
            from apps.feedback.models import Feedback
            avg = Feedback.objects.filter(
                rating__isnull=False,
            ).aggregate(avg=Avg("rating"))["avg"]
            if avg is not None:
                rating = round(float(avg), 1)
        except (ImportError, Exception):
            # Fallback kwa default rating
            pass

        data = {
            "users": users_count,
            "properties": properties_count,
            "rating": rating,
        }

        cache.set(STATS_CACHE_KEY, data, STATS_CACHE_TTL)
        return Response(data)