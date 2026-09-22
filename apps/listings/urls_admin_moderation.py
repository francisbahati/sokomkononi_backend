"""
Alias routes so that frontends whose axios interceptor attaches the
JWT only to /api/admin/* also work for listing moderation.

Mounts:
    GET  /api/admin/listings/pending/
    POST /api/admin/listings/{listing_id}/approve/
    POST /api/admin/listings/{listing_id}/reject/
"""
from django.urls import path

from .views import (
    AdminApproveListingView,
    AdminPendingListingsView,
    AdminRejectListingView,
)


urlpatterns = [
    path(
        "pending/",
        AdminPendingListingsView.as_view(),
        name="admin-listings-pending",
    ),
    path(
        "<int:listing_id>/approve/",
        AdminApproveListingView.as_view(),
        name="admin-listings-approve",
    ),
    path(
        "<int:listing_id>/reject/",
        AdminRejectListingView.as_view(),
        name="admin-listings-reject",
    ),
]
