from django.urls import path

from .views import (
    TrashEmptyAllView,
    TrashEmptyByTypeView,
    TrashListView,
    TrashOverviewView,
    TrashPermanentDeleteView,
    TrashRestoreView,
)


urlpatterns = [
    path("overview/", TrashOverviewView.as_view(), name="trash-overview"),
    path("empty/", TrashEmptyAllView.as_view(), name="trash-empty-all"),
    path("<str:type>/", TrashListView.as_view(), name="trash-list"),
    path("<str:type>/empty/", TrashEmptyByTypeView.as_view(), name="trash-empty-type"),
    path(
        "<str:type>/<int:pk>/restore/",
        TrashRestoreView.as_view(),
        name="trash-restore",
    ),
    path(
        "<str:type>/<int:pk>/",
        TrashPermanentDeleteView.as_view(),
        name="trash-permanent-delete",
    ),
]
