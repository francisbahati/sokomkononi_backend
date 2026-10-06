from django.urls import path

from .views import ReservationRateViewSet


urlpatterns = [
    # Root — GET (list), PATCH (partial_update), POST (create)
    path(
        "",
        ReservationRateViewSet.as_view({
            "get": "list",
            "patch": "partial_update",
            "post": "partial_update",
        }),
        name="reservation-rates",
    ),
    # Toggle — POST
    path(
        "toggle/",
        ReservationRateViewSet.as_view({"post": "toggle"}),
        name="reservation-rate-toggle",
    ),
]