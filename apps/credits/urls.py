from django.urls import include, path
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import UserCreditViewSet


router = DefaultRouter()
router.register(r"", UserCreditViewSet, basename="credit")


urlpatterns = [
    path("", include(router.urls)),
]
