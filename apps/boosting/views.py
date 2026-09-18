from django.shortcuts import get_object_or_404

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from drf_spectacular.utils import OpenApiResponse, extend_schema

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


class BoostPackageViewSet(
    SoftDeleteViewSetMixin,
    viewsets.ReadOnlyModelViewSet,
):
    serializer_class = BoostPackageSerializer
    permission_classes = [permissions.AllowAny]

    queryset = BoostPackage.objects.none()

    def get_queryset(self):
        # drf-spectacular calls get_queryset() during schema generation.
        if getattr(self, "swagger_fake_view", False):
            return BoostPackage.objects.none()

        qs = BoostPackage.objects.all()
        user = self.request.user
        if user.is_authenticated and user.is_staff:
            return qs
        return qs.filter(is_active=True)

    def _can_restore(self, instance):
        return bool(
            self.request.user.is_authenticated
            and self.request.user.is_staff
        )

    def get_permissions(self):
        if self.action in ["trash", "restore"]:
            return [permissions.IsAdminUser()]
        return super().get_permissions()


class ListingBoostViewSet(viewsets.ModelViewSet):
    serializer_class = ListingBoostSerializer
    permission_classes = [permissions.IsAuthenticated]

    http_method_names = ["get", "post", "head", "options"]

    # Placeholder for drf-spectacular.
    queryset = ListingBoost.objects.none()

    def get_queryset(self):
        # drf-spectacular calls get_queryset() during schema generation.
        if getattr(self, "swagger_fake_view", False):
            return ListingBoost.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            return ListingBoost.objects.none()

        qs = ListingBoost.objects.select_related(
            "listing", "seller", "package",
        )
        if user.is_staff:
            return qs
        return qs.filter(seller=user)

    @extend_schema(
        request=BoostCreateSerializer,
        responses={201: ListingBoostSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = BoostCreateSerializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        listing = get_object_or_404(
            Listing.objects.select_related("seller"),
            pk=serializer.validated_data["listing"],
        )

        boost = create_boost(
            listing=listing,
            user=request.user,
            package=serializer.validated_data["package"],
        )

        return Response(
            ListingBoostSerializer(boost, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        responses=ListingBoostSerializer(many=True),
    )
    @action(detail=False, methods=["get"], url_path="my")
    def my_boosts(self, request):
        qs = (
            ListingBoost.objects
            .select_related("listing", "seller", "package")
            .filter(seller=request.user)
        )
        return Response(self.get_serializer(qs, many=True).data)

    @extend_schema(
        request=BoostPaymentSerializer,
        responses={200: ListingBoostSerializer},
    )
    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        boost = get_object_or_404(self.get_queryset(), pk=pk)

        serializer = BoostPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        boost = mark_boost_as_paid(
            boost=boost,
            payment_reference=serializer.validated_data["payment_reference"],
        )

        return Response(
            self.get_serializer(boost).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=None,
        responses={200: ListingBoostSerializer},
    )
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        boost = get_object_or_404(self.get_queryset(), pk=pk)
        boost = activate_boost(boost=boost)
        return Response(
            self.get_serializer(boost).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=BoostCancelSerializer,
        responses={200: ListingBoostSerializer},
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        boost = get_object_or_404(self.get_queryset(), pk=pk)

        serializer = BoostCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        boost = cancel_boost(boost=boost, user=request.user)

        return Response(
            self.get_serializer(boost).data,
            status=status.HTTP_200_OK,
        )