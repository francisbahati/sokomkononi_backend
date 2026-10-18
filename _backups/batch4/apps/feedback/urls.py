from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import FeedbackViewSet


router = SimpleRouter()
router.register(r"", FeedbackViewSet, basename="feedback")


urlpatterns = [
    path("", include(router.urls)),
]
