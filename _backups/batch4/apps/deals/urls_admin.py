# apps/deals/urls_admin.py
from django.urls import path

from .views_admin import AdminDealRoomViewSet


urlpatterns = [
    path(
        "",
        AdminDealRoomViewSet.as_view({"get": "list"}),
        name="admin-deals-list",
    ),
    path(
        "<int:pk>/",
        AdminDealRoomViewSet.as_view({"get": "retrieve"}),
        name="admin-deals-detail",
    ),
]