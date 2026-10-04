from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiResponse, extend_schema

from apps.core.mixins import SoftDeleteViewSetMixin
from apps.credits.services import consume_credit
from apps.listings.models import Listing

from .models import BoostFeeConfig, BoostPackage, ListingBoost
from .serializers import (
    BoostCancelSerializer,
    BoostCreateSerializer,
    BoostFeeConfigSerializer,
    BoostPackageSerializer,
    BoostPaymentSerializer,
    ListingBoostSerializer,
)
from .services.boost import (
    activate_boost,
    cancel_boost,
    create_boost,
    is_boost_fee_enabled,
    mark_boost_as_paid,
    initiate_boost_payment,
    pay_boost_free,
)


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class BoostPackageViewSet(
    SoftDeleteViewSetMixin,
    viewsets.ModelViewSet,
):
    serializer_class = BoostPackageSerializer
    permission_classes = [IsAdminOrReadOnly]

    queryset = BoostPackage.objects.none()

    def get_queryset(self):
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


class BoostFeeConfigView(APIView):
    """
    GET   /boosting/fee-config/  -> anyone: is the boost fee enabled?
    PATCH /boosting/fee-config/  -> admin only: {"is_active": true|false}
    """

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    @extend_schema(responses=BoostFeeConfigSerializer)
    def get(self, request):
        return Response(
            BoostFeeConfigSerializer(BoostFeeConfig.get_solo()).data
        )

    @extend_schema(
        request=BoostFeeConfigSerializer,
        responses=BoostFeeConfigSerializer,
    )
    def patch(self, request):
        serializer = BoostFeeConfigSerializer(
            BoostFeeConfig.get_solo(), data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ListingBoostViewSet(viewsets.ModelViewSet):
    serializer_class = ListingBoostSerializer
    permission_classes = [permissions.IsAuthenticated]

    http_method_names = ["get", "post", "head", "options"]

    queryset = ListingBoost.objects.none()

    def get_queryset(self):
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

    @extend_schema(responses=ListingBoostSerializer(many=True))
    @action(detail=False, methods=["get"], url_path="my")
    def my_boosts(self, request):
        qs = (
            ListingBoost.objects
            .select_related("listing", "seller", "package")
            .filter(seller=request.user)
        )
        return Response(self.get_serializer(qs, many=True).data)

    @extend_schema(request=None, responses={201: ListingBoostSerializer})
    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        boost = get_object_or_404(self.get_queryset(), pk=pk)

        # ── Free path: boost fee disabled by admin ──────────────
        # No payment and no credit is consumed, whatever the client sent.
        if not is_boost_fee_enabled():
            boost = pay_boost_free(boost=boost, user=request.user)
            if boost.status != ListingBoost.BoostStatus.ACTIVE:
                boost = activate_boost(boost=boost)
            return Response(
                {
                    "payment_status": "SUCCESS",
                    "via": "free",
                    "boost": ListingBoostSerializer(
                        boost, context={"request": request}
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        # ── Credits path ────────────────────────────────────────
        payment_reference = (request.data.get("payment_reference") or "").strip()
        if payment_reference == "credits":
            # Atomic: if marking paid / activating fails, the credit
            # is rolled back instead of being lost.
            with transaction.atomic():
                if not consume_credit(request.user, "boost"):
                    return Response(
                        {"detail": "Hakuna boost credits za kutosha."},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
                boost = mark_boost_as_paid(
                    boost=boost, payment_reference="credits",
                )
                boost = activate_boost(boost=boost)
            return Response(
                {
                    "payment_status": "SUCCESS",
                    "via": "credits",
                    "boost": ListingBoostSerializer(
                        boost, context={"request": request}
                    ).data,
                },
                status=status.HTTP_200_OK,
            )

        # ── Default: FimiPay ────────────────────────────────────
        data = initiate_boost_payment(
            boost=boost, user=request.user,
            payment_method=request.data.get("payment_method", "mobile"),
            phone=request.data.get("phone", ""),
        )
        return Response({
            "boost_id": boost.id,
            "payment_status": (data.get("payment_status") or "PENDING"),
            "fimipay": data,
        }, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=None,
        responses={200: ListingBoostSerializer},
    )
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        boost = get_object_or_404(self.get_queryset(), pk=pk)
        # Idempotent: the webhook may already have activated it.
        if boost.status != ListingBoost.BoostStatus.ACTIVE:
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