from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    AdminApproveListingView,
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


fee_rules_router = SimpleRouter()
fee_rules_router.register(
    r"", ListingFeeRuleViewSet, basename="listing-fee-rule",
)


listing_list = ListingViewSet.as_view({
    "get": "list", "post": "create",
})
listing_detail = ListingViewSet.as_view({
    "get": "retrieve", "put": "update",
    "patch": "partial_update", "delete": "destroy",
})

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
admin_approve_listing = AdminApproveListingView.as_view()
admin_reject_listing = AdminRejectListingView.as_view()


urlpatterns = [
    # Fee rules must come before <int:pk>/ catch-all
    path("fee-rules/", include(fee_rules_router.urls)),

    # Admin moderation (must come before <int:pk>/ to avoid being captured)
    path("admin/pending/", admin_pending_listings, name="admin-pending-listings"),

    path("", listing_list, name="listing-list"),
    path("<int:pk>/", listing_detail, name="listing-detail"),

    path("<int:listing_id>/property-details/", property_detail_list,
         name="property-details-create"),
    path("<int:listing_id>/property-details/detail/", property_detail,
         name="property-details"),

    path("<int:listing_id>/land-details/", land_detail_list,
         name="land-details-create"),
    path("<int:listing_id>/land-details/detail/", land_detail, name="land-details"),

    path("<int:listing_id>/vehicle-details/", vehicle_detail_list,
         name="vehicle-details-create"),
    path("<int:listing_id>/vehicle-details/detail/", vehicle_detail,
         name="vehicle-details"),

    path("<int:listing_id>/business-details/", business_detail_list,
         name="business-details-create"),
    path("<int:listing_id>/business-details/detail/", business_detail,
         name="business-details"),

    path("<int:listing_id>/equipment-details/", equipment_detail_list,
         name="equipment-details-create"),
    path("<int:listing_id>/equipment-details/detail/", equipment_detail,
         name="equipment-details"),

    path("<int:listing_id>/images/", listing_image_list,
         name="listing-image-list"),
    path("<int:listing_id>/images/<int:pk>/", listing_image_detail,
         name="listing-image-detail"),

    path("<int:listing_id>/fee/", listing_fee_view, name="listing-fee"),
    path("<int:listing_id>/fee/pay/", listing_fee_payment_view,
         name="listing-fee-pay"),

    path("<int:listing_id>/approve/", admin_approve_listing,
         name="admin-approve-listing"),
    path("<int:listing_id>/reject/", admin_reject_listing,
         name="admin-reject-listing"),
]