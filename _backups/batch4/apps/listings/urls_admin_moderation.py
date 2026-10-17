from django.urls import path

from .views import (
    AdminApproveListingView,
    AdminFinalizeApprovalView,
    AdminPendingListingsView,
    AdminRejectListingView,
    AdminRequestEditListingView,
    AdminRequestPaymentListingView,
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
    path(
        "<int:listing_id>/request-edit/",
        AdminRequestEditListingView.as_view(),
        name="admin-listings-request-edit",
    ),
    path(
        "<int:listing_id>/request-payment/",
        AdminRequestPaymentListingView.as_view(),
        name="admin-listings-request-payment",
    ),
    path(
        "<int:listing_id>/finalize-approval/",
        AdminFinalizeApprovalView.as_view(),
        name="admin-listings-finalize-approval",
    ),
]