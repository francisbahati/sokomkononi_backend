from django.urls import path
from .views import TrashOverviewView

urlpatterns = [
    path("overview/", TrashOverviewView.as_view(), name="trash-overview"),
]