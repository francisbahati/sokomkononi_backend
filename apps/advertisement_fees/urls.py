from django.urls import path

from .views import AdvertisementFeeConfigViewSet


urlpatterns = [
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
