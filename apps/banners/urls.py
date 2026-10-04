from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BannerAdViewSet


router = DefaultRouter()
router.register(r"", BannerAdViewSet, basename="banner")


urlpatterns = [
    path("", include(router.urls)),
]
