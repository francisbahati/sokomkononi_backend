from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BundlePurchaseViewSet, BundleViewSet


bundles_router = DefaultRouter()
bundles_router.register(r"purchases", BundlePurchaseViewSet, basename="bundle-purchase")
bundles_router.register(r"", BundleViewSet, basename="bundle")


urlpatterns = [
    path("", include(bundles_router.urls)),
]
