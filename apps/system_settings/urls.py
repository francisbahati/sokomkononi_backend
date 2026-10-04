from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AppStoreLinksView,
    PlatformPolicyView,
    WebhookViewSet,
)


webhooks_router = DefaultRouter()
webhooks_router.register(r"", WebhookViewSet, basename="webhook")


# Alias: /api/system-settings/sub-admins/ -> RBAC StaffViewSet
# (preserves the legacy frontend URL; single implementation lives in RBAC)
from rest_framework.routers import DefaultRouter as _DefaultRouter
from apps.rbac.views import StaffViewSet as _StaffViewSet

_sub_admins_router = _DefaultRouter()
_sub_admins_router.register(r"", _StaffViewSet, basename="system-settings-sub-admin")


urlpatterns = [
    path("webhooks/", include(webhooks_router.urls)),
    path("sub-admins/", include(_sub_admins_router.urls)),
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
