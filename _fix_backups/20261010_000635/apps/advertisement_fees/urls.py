# apps/advertisement_fees/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdvertisementFeeConfigViewSet,
    AdvertisementPackageViewSet,
)


package_router = DefaultRouter()
package_router.register(r"", AdvertisementPackageViewSet, basename="advertisement-package")


urlpatterns = [
    path(
        "toggle/",
        AdvertisementFeeConfigViewSet.as_view({"post": "toggle"}),
        name="advertisement-fee-toggle",
    ),
    path(
        "",
        AdvertisementFeeConfigViewSet.as_view({
            "get": "list",
            "post": "create",
            "patch": "partial_update",
        }),
        name="advertisement-fee-config",
    ),
    path("packages/", include(package_router.urls)),
]