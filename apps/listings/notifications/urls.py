from django.urls import include, path
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import NotificationViewSet


router = DefaultRouter()

router.register(
    r"",
    NotificationViewSet,
    basename="notification",
)

urlpatterns = [
    path(
        "",
        include(router.urls),
    ),
]