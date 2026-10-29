# apps/banners/urls.py
from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    BannerAdViewSet,
    CampaignViewSet,
    PromotionsAnalyticsView,
)


# ============================================================
# CAMPAIGNS ROUTER
# ============================================================
campaign_router = SimpleRouter()
campaign_router.register(r"campaigns", CampaignViewSet, basename="campaign")


# ============================================================
# BANNERS ROUTER
# ============================================================
# SimpleRouter (sio DefaultRouter) — inaunda URLs zote ikiwa ni
# pamoja na @action (status/<listing_id>/, cancel/, pay/).
# SimpleRouter haina api-root view, hivyo POST /api/banners/ haitakuwa 405.
# ============================================================
banner_router = SimpleRouter()
banner_router.register(r"", BannerAdViewSet, basename="banner")


# ============================================================
# URL PATTERNS
# ============================================================
urlpatterns = [
    # Analytics — /api/banners/analytics/
    path(
        "analytics/",
        PromotionsAnalyticsView.as_view({"get": "list"}),
        name="promotions-analytics",
    ),

    # Campaigns CRUD — /api/banners/campaigns/
    path("", include(campaign_router.urls)),

    # Banners CRUD + @actions — /api/banners/
    path("", include(banner_router.urls)),
]