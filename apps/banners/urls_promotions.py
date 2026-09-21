from django.urls import path

from .views_promotions import (
    CampaignViewSet,
    PromotionsAnalyticsView,
)


urlpatterns = [
    path(
        "analytics/",
        PromotionsAnalyticsView.as_view({"get": "list"}),
        name="promotions-analytics",
    ),
    path(
        "campaigns/",
        CampaignViewSet.as_view({"get": "list", "post": "create"}),
        name="promotions-campaigns",
    ),
    path(
        "campaigns/<int:pk>/",
        CampaignViewSet.as_view({
            "get": "list",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="promotions-campaign-detail",
    ),
]
