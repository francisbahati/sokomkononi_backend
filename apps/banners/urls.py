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
# Tumia SimpleRouter (sio DefaultRouter) ili kuepuka api-root
# view kwenye "" — hiyo ilikuwa inasababisha 405 Method Not Allowed
# kwa POST /api/banners/.
# ============================================================
campaign_router = SimpleRouter()
campaign_router.register(r"campaigns", CampaignViewSet, basename="campaign")


# ============================================================
# BANNER ROUTES (explicit — bila router)
# ============================================================
banner_urls = [
    path(
        "",
        BannerAdViewSet.as_view({"get": "list", "post": "create"}),
        name="banner-list",
    ),
    path(
        "<int:pk>/",
        BannerAdViewSet.as_view({
            "get": "retrieve",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="banner-detail",
    ),
    path(
        "<int:pk>/pay/",
        BannerAdViewSet.as_view({"post": "pay"}),
        name="banner-pay",
    ),
]


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

    # Banners CRUD — /api/banners/ (MWISHO — catch-all)
    path("", include((banner_urls, "banner"))),
]