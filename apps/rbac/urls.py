from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RoleViewSet, StaffViewSet


roles_router = DefaultRouter()
roles_router.register(r"", RoleViewSet, basename="role")

staff_router = DefaultRouter()
staff_router.register(r"", StaffViewSet, basename="staff")


urlpatterns = [
    path("roles/", include(roles_router.urls)),
    path("staff/", include(staff_router.urls)),
]