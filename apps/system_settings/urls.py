from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppStoreLinksView,
    PlatformPolicyView,
    WebhookViewSet,
)


webhooks_router = DefaultRouter()
webhooks_router.register(r"", WebhookViewSet, basename="webhook")


urlpatterns = [
    path("webhooks/", include(webhooks_router.urls)),
    path(
        "app-store-links/",
        AppStoreLinksView.as_view({"get": "list", "post": "create"}),
        name="app-store-links",
    ),
    path(
        "platform-policy/",
        PlatformPolicyView.as_view({"get": "list", "post": "create"}),
        name="platform-policy",
    ),
]