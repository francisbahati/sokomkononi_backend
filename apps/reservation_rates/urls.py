from django.urls import path

from .views import ReservationRateViewSet


urlpatterns = [
    path(
        "",
        ReservationRateViewSet.as_view({"get": "list"}),
        name="reservation-rates",
    ),
    path(
        "<str:pk>/",
        ReservationRateViewSet.as_view({"patch": "partial_update"}),
        name="reservation-rate-detail",
    ),
]
