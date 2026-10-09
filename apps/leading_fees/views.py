# apps/leading_fees/views.py
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.credits.services import consume_credit
from apps.listings.models import Listing

from .models import LeadingFeeConfig, LeadingPackage, ListingLeading
from .serializers import (
    LeadingApplySerializer,
    LeadingFeeConfigSerializer,
    LeadingPackageSerializer,
    LeadingPaymentSerializer,
    ListingLeadingSerializer,
)
from .services import create_leading, initiate_leading_payment


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class LeadingFeeConfigViewSet(viewsets.GenericViewSet):
    """
    Singleton viewset — LeadingFeeConfig moja (pk=1).

    GET     /api/leading-fees/             → config
    PATCH   /api/leading-fees/             → update config
    POST    /api/leading-fees/toggle/      → toggle is_enabled
    """
    queryset = LeadingFeeConfig.objects.all()
    serializer_class = LeadingFeeConfigSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_object(self):
        return LeadingFeeConfig.get_solo()

    def list(self, request):
        obj = self.get_object()
        return Response(LeadingFeeConfigSerializer(obj).data)

    def create(self, request):
        obj = self.get_object()
        serializer = LeadingFeeConfigSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def partial_update(self, request, pk=None):
        obj = self.get_object()
        serializer = LeadingFeeConfigSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="toggle")
    def toggle(self, request):
        obj = self.get_object()
        obj.is_enabled = not obj.is_enabled
        obj.save(update_fields=["is_enabled", "updated_at"])
        return Response({"is_enabled": obj.is_enabled})


class LeadingPackageViewSet(viewsets.ModelViewSet):
    """
    CRUD kwa Leading Packages.

    GET    /api/leading-fees/packages/           → list
    POST   /api/leading-fees/packages/           → create
    PATCH  /api/leading-fees/packages/{id}/      → update
    DELETE /api/leading-fees/packages/{id}/      → delete
    POST   /api/leading-fees/packages/{id}/toggle/ → toggle is_active
    """
    serializer_class = LeadingPackageSerializer
    permission_classes = [IsAdminOrReadOnly]
    queryset = LeadingPackage.objects.all()

    def get_queryset(self):
        qs = LeadingPackage.objects.all()
        user = self.request.user
        if user.is_authenticated and user.is_staff:
            return qs
        return qs.filter(is_active=True)

    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, pk=None):
        pkg = self.get_object()
        pkg.is_active = not pkg.is_active
        pkg.save(update_fields=["is_active", "updated_at"])
        return Response({"is_active": pkg.is_active})


class ListingLeadingViewSet(viewsets.ModelViewSet):
    queryset = ListingLeading.objects.select_related("listing", "seller", "package")
    serializer_class = ListingLeadingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ListingLeading.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            return ListingLeading.objects.none()

        qs = ListingLeading.objects.select_related("listing", "seller", "package")
        if user.is_staff:
            return qs
        return qs.filter(seller=user)

    @action(detail=False, methods=["post"], url_path="apply")
    def apply(self, request):
        serializer = LeadingApplySerializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        listing = get_object_or_404(
            Listing.objects.select_related("seller"),
            pk=serializer.validated_data["listing"],
        )
        package = get_object_or_404(
            LeadingPackage,
            pk=serializer.validated_data["package"],
            is_active=True,
        )

        leading = create_leading(
            listing_id=listing.id,
            user=request.user,
            package=package,
        )

        return Response(
            ListingLeadingSerializer(leading, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        leading = get_object_or_404(self.get_queryset(), pk=pk)
        if leading.seller_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "Huna ruhusa."}, status=status.HTTP_403_FORBIDDEN)

        payment_reference = (request.data.get("payment_reference") or "").strip()
        if payment_reference == "credits":
            import uuid
            from django.db import transaction

            with transaction.atomic():
                if not consume_credit(user=request.user, service_key="leading"):
                    return Response(
                        {"detail": "Hakuna leading credits za kutosha."},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
                now = timezone.now()
                leading.payment_status = "PAID"
                leading.payment_reference = f"credits-{leading.pk}-{uuid.uuid4().hex[:12]}"
                leading.paid_at = now
                leading.status = "ACTIVE"
                leading.starts_at = now
                hours = leading.package.duration_hours if leading.package else (leading.days or 7) * 24
                leading.expires_at = now + timedelta(hours=hours)
                leading.save(update_fields=[
                    "payment_status", "payment_reference",
                    "paid_at", "status", "starts_at",
                    "expires_at", "updated_at",
                ])
            return Response(
                {
                    "payment_status": "SUCCESS",
                    "via": "credits",
                    "purchase": ListingLeadingSerializer(leading, context={"request": request}).data,
                },
                status=status.HTTP_200_OK,
            )

        data = initiate_leading_payment(
            leading=leading,
            user=request.user,
            payment_method=request.data.get("payment_method", "mobile"),
            phone=request.data.get("phone", ""),
        )
        return Response({
            "purchase_id": leading.id,
            "payment_status": (data.get("payment_status") or "PENDING"),
            "fimipay": data,
        }, status=status.HTTP_201_CREATED)