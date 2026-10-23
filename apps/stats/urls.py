from django.urls import path

from .views import PublicStatsView


app_name = "stats"


urlpatterns = [
    path("public/", PublicStatsView.as_view(), name="public-stats"),
]