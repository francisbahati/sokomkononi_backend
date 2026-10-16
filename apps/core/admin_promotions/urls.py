# apps/core/admin_promotions/urls.py
from django.urls import path

from .views import AdminPromotionActionView


urlpatterns = [
    path(
        "<str:type>/<int:id>/<str:action>/",
        AdminPromotionActionView.as_view(),
        name="admin-promotion-action",
    ),
]