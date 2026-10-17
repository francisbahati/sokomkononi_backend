from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import SavedListingViewSet
from .views_extra import saved_toggle, saved_by_listing

router = DefaultRouter()
router.register(r"", SavedListingViewSet, basename="saved-listing")

# IMPORTANT: extra routes go BEFORE router.urls so that `toggle/` and
# `listing/1/` are not interpreted as a `<pk>` by the router.
urlpatterns = [
    path("toggle/", saved_toggle, name="saved-toggle"),
    path("listing/<int:listing_id>/", saved_by_listing, name="saved-by-listing"),
] + router.urls
