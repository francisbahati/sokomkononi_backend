from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BannerAdViewSet


router = DefaultRouter()
router.register(r"", BannerAdViewSet, basename="banner")


urlpatterns = [
    path("", include(router.urls)),
]

# Admin promotions aggregate
from django.urls import path as _path
from .views_admin import AdminPromotionsView

urlpatterns += [
    _path("admin/promotions/", AdminPromotionsView.as_view(),
          name="admin-promotions"),
]
