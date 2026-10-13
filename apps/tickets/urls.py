from django.urls import include, path
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import TicketViewSet


router = DefaultRouter()
router.register(r"", TicketViewSet, basename="ticket")


urlpatterns = [
    path("", include(router.urls)),
]