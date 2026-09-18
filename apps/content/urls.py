from django.urls import path

from .views import ContentViewSet


urlpatterns = [
    path("", ContentViewSet.as_view({"get": "list"}), name="content-list"),
    path(
        "section/<slug:key>/",
        ContentViewSet.as_view({"get": "by_key"}),
        name="content-by-key",
    ),
]
