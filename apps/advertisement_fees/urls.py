# apps/advertisement_fees/urls.py
from django.urls import path

from .views import AdvertisementFeeConfigViewSet


urlpatterns = [
    path(
        "toggle/",
        AdvertisementFeeConfigViewSet.as_view({"post": "toggle"}),
        name="advertisement-fee-toggle",
    ),
    path(
        "",
        AdvertisementFeeConfigViewSet.as_view({
            "get": "list",
            "post": "create",
            "patch": "partial_update",
        }),
        name="advertisement-fee-config",
    ),
]