from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SavedListingViewSet


router = DefaultRouter()
router.register(r"", SavedListingViewSet, basename="saved-listing")


urlpatterns = [
    path("", include(router.urls)),
]