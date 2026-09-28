from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LeadingFeeConfigViewSet, ListingLeadingViewSet


purchase_router = DefaultRouter()
purchase_router.register(r"", ListingLeadingViewSet, basename="listing-leading")


urlpatterns = [
    path(
        "",
        LeadingFeeConfigViewSet.as_view({
            "get": "list",
            "post": "create",
            "patch": "partial_update",
        }),
        name="leading-fee-config",
    ),
    path("purchases/", include(purchase_router.urls)),
]
