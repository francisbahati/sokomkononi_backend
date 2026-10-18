"""Public promotions routes — delegate to the canonical CampaignViewSet."""
from django.urls import path

from .views import CampaignViewSet, PromotionsAnalyticsView


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
            "get": "retrieve",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="promotions-campaign-detail",
    ),
    path(
        "campaigns/<int:pk>/toggle/",
        CampaignViewSet.as_view({"post": "toggle"}),
        name="promotions-campaign-toggle",
    ),
]
