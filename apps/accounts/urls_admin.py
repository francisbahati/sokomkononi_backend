from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_admin import AdminUserViewSet
from .views_admin_extra import AdminUserFullView


router = DefaultRouter()
router.register(r"", AdminUserViewSet, basename="admin-user")


urlpatterns = [
    path("", include(router.urls)),
    path(
        "<int:pk>/full/",
        AdminUserFullView.as_view(),
        name="admin-user-full",
    ),
]