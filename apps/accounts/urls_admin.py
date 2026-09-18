from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_admin import AdminUserViewSet


router = DefaultRouter()
router.register(r"", AdminUserViewSet, basename="admin-user")


urlpatterns = [
    path("", include(router.urls)),
]