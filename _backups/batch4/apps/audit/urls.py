from django.urls import include, path
from rest_framework.routers import SimpleRouter as DefaultRouter

from .views import AuditLogViewSet


router = DefaultRouter()
router.register(r"", AuditLogViewSet, basename="audit-log")


urlpatterns = [
    path("", include(router.urls)),
]