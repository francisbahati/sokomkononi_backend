from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
)

from apps.core.mixins import SoftDeleteViewSetMixin
from apps.listings.models import Listing

from .models import BoostPackage, ListingBoost
from .serializers import (
    BoostCancelSerializer,
    BoostCreateSerializer,
    BoostPackageSerializer,
    BoostPaymentSerializer,
    ListingBoostSerializer,
)
from .services.boost import (
    activate_boost,
    cancel_boost,
    create_boost,
    mark_boost_as_paid,
)


# ============================================================================
# BOOST PACKAGE VIEWSET
# ============================================================================

class BoostPackageViewSet(
    SoftDeleteViewSetMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """
    Public endpoint for available boost packages.

    Admin can see all packages.
    Normal users only see active packages.
    """

    serializer_class = BoostPackageSerializer
    permission_classes = [permissions.AllowAny]

    owner_field = "id"  # not used; only staff restore

    def get_queryset(self):
        queryset = BoostPackage.objects.all()

        if self.request.user.is_staff:
            return queryset

        return queryset.filter(is_active=True)

    def _can_restore(self, instance):
        return bool(
            self.request.user.is_authenticated
            and self.request.user.is_staff
        )

    def get_permissions(self):
        if self.action in ["trash", "restore"]:
            return [permissions.IsAdminUser()]

        return super().get_permissions()


# ============================================================================
# LISTING BOOST VIEWSET
# ============================================================================

class ListingBoostViewSet(viewsets.ModelViewSet):
    """
    Manage listing boosts.

    Seller:
        - create boost
        - view own boosts
        - pay boost
        - activate paid boost
        - cancel pending boost

    Admin:
        - view all boosts
        - manage all boosts
    """

    serializer_class = ListingBoostSerializer
    permission_classes = [
        permissions.IsAuthenticated,
    ]

    http_method_names = [
        "get",
        "post",
        "head",
        "options",
    ]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return (
                ListingBoost.objects
                .select_related(
                    "listing",
                    "seller",
                    "package",
                )
                .all()
            )

        return (
            ListingBoost.objects
            .select_related(
                "listing",
                "seller",
                "package",
            )
            .filter(seller=user)
        )

    @extend_schema(
        request=BoostCreateSerializer,
        responses={
            201: ListingBoostSerializer,
            400: OpenApiResponse(
                description="Boost request haikubaliki.",
            ),
        },
        summary="Create boost request",
        description=(
            "Seller anaweza kuanzisha boost kwa listing yake "
            "iliyo AVAILABLE."
        ),
    )
    def create(self, request, *args, **kwargs):
        serializer = BoostCreateSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        listing_id = serializer.validated_data["listing"]
        package = serializer.validated_data["package"]

        listing = get_object_or_404(
            Listing.objects.select_related("seller"),
            pk=listing_id,
        )

        try:
            boost = create_boost(
                listing=listing,
                user=request.user,
                package=package,
            )
        except Exception as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        output = ListingBoostSerializer(
            boost,
            context={"request": request},
        )

        return Response(
            output.data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses=ListingBoostSerializer(many=True),
        summary="Get my boosts",
        description="Returns all boosts belonging to the authenticated seller.",
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="my",
    )
    def my_boosts(self, request):
        queryset = (
            ListingBoost.objects
            .select_related(
                "listing",
                "seller",
                "package",
            )
            .filter(seller=request.user)
        )

        serializer = self.get_serializer(
            queryset,
            many=True,
        )

        return Response(serializer.data)

    @extend_schema(
        request=BoostPaymentSerializer,
        responses={
            200: ListingBoostSerializer,
            400: OpenApiResponse(
                description="Payment haikukamilika.",
            ),
        },
        summary="Pay for boost",
        description=(
            "Development endpoint inayorekodi payment reference "
            "na kuweka boost kuwa PAID. Payment gateway halisi "
            "itaunganishwa baadaye."
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="pay",
    )
    def pay(self, request, pk=None):
        boost = get_object_or_404(
            self.get_queryset(),
            pk=pk,
        )

        serializer = BoostPaymentSerializer(
            data=request.data,
        )

        serializer.is_valid(raise_exception=True)

        try:
            boost = mark_boost_as_paid(
                boost=boost,
                payment_reference=serializer.validated_data[
                    "payment_reference"
                ],
            )
        except Exception as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        output = self.get_serializer(boost)

        return Response(
            output.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=None,
        responses={
            200: ListingBoostSerializer,
            400: OpenApiResponse(
                description="Boost haikuweza ku-activate.",
            ),
        },
        summary="Activate boost",
        description=(
            "Activates a paid boost and updates the listing "
            "with is_boosted=True and boosted_until."
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="activate",
    )
    def activate(self, request, pk=None):
        boost = get_object_or_404(
            self.get_queryset(),
            pk=pk,
        )

        try:
            boost = activate_boost(
                boost=boost,
            )
        except Exception as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        output = self.get_serializer(boost)

        return Response(
            output.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=BoostCancelSerializer,
        responses={
            200: ListingBoostSerializer,
            400: OpenApiResponse(
                description="Boost haikuweza ku-cancel.",
            ),
        },
        summary="Cancel boost",
        description=(
            "Cancels a pending unpaid boost."
        ),
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="cancel",
    )
    def cancel(self, request, pk=None):
        boost = get_object_or_404(
            self.get_queryset(),
            pk=pk,
        )

        serializer = BoostCancelSerializer(
            data=request.data,
        )

        serializer.is_valid(raise_exception=True)

        try:
            boost = cancel_boost(
                boost=boost,
                user=request.user,
            )
        except Exception as exc:
            return Response(
                {
                    "detail": str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        output = self.get_serializer(boost)

        return Response(
            output.data,
            status=status.HTTP_200_OK,
        )