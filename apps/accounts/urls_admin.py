from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views_admin import AdminUserViewSet


router = DefaultRouter()
router.register(r"", AdminUserViewSet, basename="admin-user")


urlpatterns = [
    path("", include(router.urls)),
]
from django.urls import path as _p
from .views_admin_extra import AdminUserFullView
urlpatterns += [
    _p("<int:pk>/full/", AdminUserFullView.as_view(), name="admin-user-full"),
]
