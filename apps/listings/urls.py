from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AdminApproveListingView,
    AdminBulkApproveView,
    AdminBulkDeleteView,
    AdminBulkRejectView,
    AdminDraftListingsView,
    AdminPendingListingsView,
    AdminRejectListingView,
    BusinessDetailsViewSet,
    EquipmentDetailsViewSet,
    LandDetailsViewSet,
    ListingFeePaymentView,
    ListingFeeView,
    ListingImageViewSet,
    ListingViewSet,
    PropertyDetailsViewSet,
    VehicleDetailsViewSet,
)
from .views_fee_rules import ListingFeeRuleViewSet
from .views_duplicate import check_duplicate_listing


fee_rules_router = SimpleRouter()
fee_rules_router.register(
    r"", ListingFeeRuleViewSet, basename="listing-fee-rule",
)


# ----------------------------------------------------------------
# ViewSet method dispatchers
# ----------------------------------------------------------------
listing_list = ListingViewSet.as_view({
    "get": "list", "post": "create",
})
listing_detail = ListingViewSet.as_view({
    "get": "retrieve", "put": "update",
    "patch": "partial_update", "delete": "destroy",
})
listing_similar = ListingViewSet.as_view({"get": "similar"})
listing_publish = ListingViewSet.as_view({"post": "publish"})
listing_pause = ListingViewSet.as_view({"post": "pause"})
listing_unpause = ListingViewSet.as_view({"post": "unpause"})
listing_mark_sold = ListingViewSet.as_view({"post": "mark_sold"})

property_detail_list = PropertyDetailsViewSet.as_view({"post": "create"})
property_detail = PropertyDetailsViewSet.as_view({
    "get": "retrieve", "put": "update",
    "patch": "partial_update", "delete": "destroy",
})

land_detail_list = LandDetailsViewSet.as_view({"post": "create"})
land_detail = LandDetailsViewSet.as_view({
    "get": "retrieve", "put": "update",
    "patch": "partial_update", "delete": "destroy",
})

vehicle_detail_list = VehicleDetailsViewSet.as_view({"post": "create"})
vehicle_detail = VehicleDetailsViewSet.as_view({
    "get": "retrieve", "put": "update",
    "patch": "partial_update", "delete": "destroy",
})

business_detail_list = BusinessDetailsViewSet.as_view({"post": "create"})
business_detail = BusinessDetailsViewSet.as_view({
    "get": "retrieve", "put": "update",
    "patch": "partial_update", "delete": "destroy",
})

equipment_detail_list = EquipmentDetailsViewSet.as_view({"post": "create"})
equipment_detail = EquipmentDetailsViewSet.as_view({
    "get": "retrieve", "put": "update",
    "patch": "partial_update", "delete": "destroy",
})

listing_image_list = ListingImageViewSet.as_view({
    "get": "list", "post": "create",
})
listing_image_detail = ListingImageViewSet.as_view({
    "get": "retrieve", "patch": "partial_update", "delete": "destroy",
})

listing_fee_view = ListingFeeView.as_view()
listing_fee_payment_view = ListingFeePaymentView.as_view()
admin_pending_listings = AdminPendingListingsView.as_view()
admin_drafts = AdminDraftListingsView.as_view()
admin_bulk_approve = AdminBulkApproveView.as_view()
admin_bulk_reject = AdminBulkRejectView.as_view()
admin_bulk_delete = AdminBulkDeleteView.as_view()
admin_approve_listing = AdminApproveListingView.as_view()
admin_reject_listing = AdminRejectListingView.as_view()


# ----------------------------------------------------------------
# URL patterns
# ----------------------------------------------------------------
urlpatterns = [
    # Fee rules must come before <int:pk>/ catch-all
    path("fee-rules/", include(fee_rules_router.urls)),

    # Duplicate check (single canonical route)
    path(
        "check-duplicate/",
        check_duplicate_listing,
        name="listing-check-duplicate",
    ),

    # Admin moderation (must come before <int:pk>/ to avoid capture)
    path(
        "admin/pending/",
        admin_pending_listings,
        name="admin-pending-listings",
    ),
    path(
        "admin/drafts/",
        admin_drafts,
        name="admin-draft-listings",
    ),
    path(
        "admin/bulk-approve/",
        admin_bulk_approve,
        name="admin-bulk-approve",
    ),
    path(
        "admin/bulk-reject/",
        admin_bulk_reject,
        name="admin-bulk-reject",
    ),
    path(
        "admin/bulk-delete/",
        admin_bulk_delete,
        name="admin-bulk-delete",
    ),

    path("", listing_list, name="listing-list"),
    path("<int:pk>/similar/", listing_similar, name="listing-similar"),
    path("<int:pk>/publish/", listing_publish, name="listing-publish"),
    path("<int:pk>/pause/", listing_pause, name="listing-pause"),
    path("<int:pk>/unpause/", listing_unpause, name="listing-unpause"),
    path("<int:pk>/mark-sold/", listing_mark_sold, name="listing-mark-sold"),
    path("<int:pk>/", listing_detail, name="listing-detail"),

    path(
        "<int:listing_id>/property-details/",
        property_detail_list,
        name="property-details-create",
    ),
    path(
        "<int:listing_id>/property-details/detail/",
        property_detail,
        name="property-details",
    ),

    path(
        "<int:listing_id>/land-details/",
        land_detail_list,
        name="land-details-create",
    ),
    path(
        "<int:listing_id>/land-details/detail/",
        land_detail,
        name="land-details",
    ),

    path(
        "<int:listing_id>/vehicle-details/",
        vehicle_detail_list,
        name="vehicle-details-create",
    ),
    path(
        "<int:listing_id>/vehicle-details/detail/",
        vehicle_detail,
        name="vehicle-details",
    ),

    path(
        "<int:listing_id>/business-details/",
        business_detail_list,
        name="business-details-create",
    ),
    path(
        "<int:listing_id>/business-details/detail/",
        business_detail,
        name="business-details",
    ),

    path(
        "<int:listing_id>/equipment-details/",
        equipment_detail_list,
        name="equipment-details-create",
    ),
    path(
        "<int:listing_id>/equipment-details/detail/",
        equipment_detail,
        name="equipment-details",
    ),

    path(
        "<str:listing_id>/images/",
        listing_image_list,
        name="listing-image-list",
    ),
    path(
        "<str:listing_id>/images/<int:pk>/",
        listing_image_detail,
        name="listing-image-detail",
    ),

    path("<str:listing_id>/fee/", listing_fee_view, name="listing-fee"),
    path(
        "<str:listing_id>/fee/pay/",
        listing_fee_payment_view,
        name="listing-fee-pay",
    ),

    path(
        "<int:listing_id>/approve/",
        admin_approve_listing,
        name="admin-approve-listing",
    ),
    path(
        "<int:listing_id>/reject/",
        admin_reject_listing,
        name="admin-reject-listing",
    ),
]
