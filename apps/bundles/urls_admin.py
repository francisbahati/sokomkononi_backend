# apps/bundles/urls_admin.py
from django.urls import path

from .views_admin import AdminBundlePurchaseViewSet

urlpatterns = [
    path(
        "purchases/",
        AdminBundlePurchaseViewSet.as_view({"get": "list"}),
        name="admin-bundle-purchases",
    ),
    path(
        "purchases/<int:pk>/",
        AdminBundlePurchaseViewSet.as_view({"get": "retrieve"}),
        name="admin-bundle-purchase-detail",
    ),
]
