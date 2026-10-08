# apps/banners/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BannerAdViewSet,
    CampaignViewSet,
    PromotionsAnalyticsView,
)


router = DefaultRouter()
router.register(r"campaigns", CampaignViewSet, basename="campaign")

analytics_router = DefaultRouter()
analytics_router.register(r"", PromotionsAnalyticsView, basename="analytics")


urlpatterns = [
    # Analytics
    path("analytics/", PromotionsAnalyticsView.as_view({"get": "list"}), name="promotions-analytics"),
    # Campaigns CRUD
    path("", include(router.urls)),
    # Banners CRUD — lazima iwe MWISHO (kwa sababu ya prefix ``)
    path("", include(([
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
    ], "banner"))),
]