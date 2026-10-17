# apps/reservation_rates/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ReservationSettingsViewSet, ReservationTierViewSet


router = DefaultRouter()
router.register(
    r"reservation-tiers",
    ReservationTierViewSet,
    basename="reservation-tier",
)


urlpatterns = [
    # Singleton settings
    path(
        "reservation-settings/",
        ReservationSettingsViewSet.as_view({
            "get": "list",
            "patch": "partial_update",
            "post": "partial_update",
        }),
        name="reservation-settings",
    ),
    path(
        "reservation-settings/toggle/",
        ReservationSettingsViewSet.as_view({"post": "toggle"}),
        name="reservation-settings-toggle",
    ),
    # Tiers CRUD
    path("", include(router.urls)),
]