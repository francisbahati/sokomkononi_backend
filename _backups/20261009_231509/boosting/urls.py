from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BoostFeeConfigView,
    BoostPackageViewSet,
    ListingBoostViewSet,
)


router = DefaultRouter()

router.register(
    r"packages",
    BoostPackageViewSet,
    basename="boost-package",
)

router.register(
    r"",
    ListingBoostViewSet,
    basename="listing-boost",
)


urlpatterns = [
    # Must come before the router: the "" prefix router would otherwise
    # capture "fee-config/" as a boost <pk>.
    path("fee-config/", BoostFeeConfigView.as_view(), name="boost-fee-config"),
    path("", include(router.urls)),
]