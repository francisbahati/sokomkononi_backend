from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppStoreLinksView,
    PlatformPolicyView,
    SubAdminViewSet,
    WebhookViewSet,
)


webhooks_router = DefaultRouter()
webhooks_router.register(r"", WebhookViewSet, basename="webhook")

sub_admins_router = DefaultRouter()
sub_admins_router.register(r"", SubAdminViewSet, basename="sub-admin")


urlpatterns = [
    path("webhooks/", include(webhooks_router.urls)),
    path("sub-admins/", include(sub_admins_router.urls)),
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
