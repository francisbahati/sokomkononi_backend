
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DealRoomViewSet


# ============================================================================
# DEAL ROOM ROUTER
# ============================================================================

router = DefaultRouter()

router.register(
    r"",
    DealRoomViewSet,
    basename="deal-room",
)


urlpatterns = [
    path("", include(router.urls)),
]
