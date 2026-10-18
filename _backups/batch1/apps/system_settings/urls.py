from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AppStoreLinksView,
    PlatformPolicyView,
    WebhookViewSet,
)

# RBAC StaffViewSet is reused so legacy frontends that hit
# /api/system-settings/sub-admins/ keep working with the same
# implementation that lives in apps.rbac.
from apps.rbac.views import StaffViewSet


webhooks_router = SimpleRouter()
webhooks_router.register(r"", WebhookViewSet, basename="webhook")

sub_admins_router = SimpleRouter()
sub_admins_router.register(r"", StaffViewSet, basename="system-settings-sub-admin")


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
