from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
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
    path("", include(router.urls)),
]