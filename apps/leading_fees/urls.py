from django.urls import path

from .views import LeadingFeeConfigViewSet


urlpatterns = [
    path(
        "",
        LeadingFeeConfigViewSet.as_view({
            "get": "list",
            "post": "create",
            "patch": "partial_update",
        }),
        name="leading-fee-config",
    ),
]
