# apps/leading_fees/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    LeadingFeeConfigViewSet,
    LeadingPackageViewSet,
    ListingLeadingViewSet,
)


package_router = DefaultRouter()
package_router.register(r"", LeadingPackageViewSet, basename="leading-package")

purchase_router = DefaultRouter()
purchase_router.register(r"", ListingLeadingViewSet, basename="listing-leading")


urlpatterns = [
    # Config toggle
    path(
        "toggle/",
        LeadingFeeConfigViewSet.as_view({"post": "toggle"}),
        name="leading-fee-toggle",
    ),
    path(
        "",
        LeadingFeeConfigViewSet.as_view({
            "get": "list",
            "post": "create",
            "patch": "partial_update",
        }),
        name="leading-fee-config",
    ),
    # Packages
    path("packages/", include(package_router.urls)),
    # Purchases
    path("purchases/", include(purchase_router.urls)),
]