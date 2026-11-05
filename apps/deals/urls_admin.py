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
    path(
        "<int:pk>/admin-message/",
        AdminDealRoomViewSet.as_view({"post": "admin_message"}),
        name="admin-deals-admin-message",
    ),
    path(
        "<int:pk>/lock/",
        AdminDealRoomViewSet.as_view({"post": "lock"}),
        name="admin-deals-lock",
    ),
    path(
        "<int:pk>/unlock/",
        AdminDealRoomViewSet.as_view({"post": "unlock"}),
        name="admin-deals-unlock",
    ),
    path(
        "<int:pk>/cancel/",
        AdminDealRoomViewSet.as_view({"post": "cancel"}),
        name="admin-deals-cancel",
    ),
]