from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import WaitingListViewSet


router = DefaultRouter()

router.register(
    r"",
    WaitingListViewSet,
    basename="waiting-list",
)

urlpatterns = [
    path(
        "",
        include(router.urls),
    ),
]