from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import LeadViewSet


router = DefaultRouter()
router.register(r"", LeadViewSet, basename="lead")


urlpatterns = [
    path("", include(router.urls)),
]