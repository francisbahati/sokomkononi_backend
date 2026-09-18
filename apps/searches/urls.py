from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SavedSearchViewSet


router = DefaultRouter()
router.register(r"", SavedSearchViewSet, basename="saved-search")


urlpatterns = [
    path("", include(router.urls)),
]