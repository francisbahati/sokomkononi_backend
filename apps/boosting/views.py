from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

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


# ============================================================
# AUDIT LOG HELPER
# ============================================================
def _log(request, action, target="", target_id=None, details="", params=None):
    """Helper — ina-logi admin action bila kuvunja request kama log inashindwa."""
    try:
        from apps.audit.services.audit import log_action
        log_action(
            request=request,
            action=action,
            target=target,
            target_id=target_id,
            details=details,
            params=params,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to write audit log: %s", action,
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

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        if response.status_code == status.HTTP_201_CREATED:
            data = response.data or {}
            _log(
                request,
                action="fee.created",
                target="BoostPackage",
                target_id=data.get("id"),
                params={"name": data.get("name") or "—"},
            )

        return response

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_snapshot = self._snapshot(instance)

        response = super().update(request, *args, **kwargs)

        if response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED,
        ):
            new_snapshot = self._snapshot(instance)
            diff = self._diff(old_snapshot, new_snapshot)
            _log(
                request,
                action="fee.updated",
                target="BoostPackage",
                target_id=instance.id,
                details={
                    "sw": f"Kifurushi cha boost '{instance.name or '—'}' kimebadilishwa ({diff})",
                    "en": f"Updated boost package '{instance.name or '—'}' ({diff})",
                },
            )

        return response

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_snapshot = self._snapshot(instance)

        response = super().partial_update(request, *args, **kwargs)

        if response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED,
        ):
            new_snapshot = self._snapshot(instance)
            diff = self._diff(old_snapshot, new_snapshot)
            _log(
                request,
                action="fee.updated",
                target="BoostPackage",
                target_id=instance.id,
                details={
                    "sw": f"Kifurushi cha boost '{instance.name or '—'}' kimebadilishwa ({diff})",
                    "en": f"Updated boost package '{instance.name or '—'}' ({diff})",
                },
            )

        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        pkg_id = instance.id
        pkg_name = instance.name

        response = super().destroy(request, *args, **kwargs)

        if response.status_code in (
            status.HTTP_204_NO_CONTENT,
            status.HTTP_200_OK,
        ):
            _log(
                request,
                action="fee.deleted",
                target="BoostPackage",
                target_id=pkg_id,
                params={"name": pkg_name},
            )

        return response

    @staticmethod
    def _snapshot(instance):
        return {
            "price": str(getattr(instance, "price", "") or ""),
            "duration_hours": str(getattr(instance, "duration_hours", "") or ""),
            "is_active": bool(getattr(instance, "is_active", True)),
            "ordering": str(getattr(instance, "ordering", "") or ""),
        }

    @staticmethod
    def _diff(old, new):
        changes = []
        for key in old:
            if old[key] != new[key]:
                changes.append(f"{key}: {old[key]} → {new[key]}")
        return ", ".join(changes) if changes else "no change"


# ✅ HAPA NDIPO ILIPOONDOLEWA KWENYE DARASA LA BoostPackageViewSet
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
        obj = BoostFeeConfig.get_solo()
        old_state = bool(obj.is_active)

        serializer = BoostFeeConfigSerializer(
            obj, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        new_state = bool(obj.is_active)
        if old_state != new_state:
            _log(
                request,
                action="fee.updated",
                target="BoostFeeConfig",
                target_id=obj.id,
                details={
                    "sw": f"Ada ya boost {'imewashwa' if new_state else 'imezimwa'}.",
                    "en": f"Boost fee {'enabled' if new_state else 'disabled'}.",
                },
            )

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
            package=serializer.validated_data.get("package"),
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

    # ── NEW: status ya boost kwa listing ──────────────────────
    @extend_schema(responses={200: None})
    @action(
        detail=False,
        methods=["get"],
        url_path=r"status/(?P<listing_id>\d+)",
        permission_classes=[permissions.IsAuthenticated],
    )
    def listing_status(self, request, listing_id=None):
        """GET /api/boosting/status/<listing_id>/"""
        listing = Listing.objects.filter(pk=listing_id).first()
        if not listing:
            return Response(
                {"detail": "Tangazo halipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if request.user.id != listing.seller_id and not request.user.is_staff:
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )

        boosts = (
            ListingBoost.objects
            .filter(listing=listing)
            .select_related("package")
            .order_by("-created_at")
        )
        active = boosts.filter(
            status=ListingBoost.BoostStatus.ACTIVE,
            expires_at__gt=timezone.now(),
        ).first()
        pending = boosts.filter(
            payment_status=ListingBoost.PaymentStatus.PENDING,
        ).first()

        return Response({
            "listing_id": listing.id,
            "has_active": bool(active),
            "active": ListingBoostSerializer(active).data if active else None,
            "has_pending": bool(pending),
            "pending": ListingBoostSerializer(pending).data if pending else None,
            "can_create_new": not active and not pending,
        })

    @extend_schema(request=None, responses={201: ListingBoostSerializer})
    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        boost = get_object_or_404(self.get_queryset(), pk=pk)

        if boost.payment_status == ListingBoost.PaymentStatus.PAID:
            return Response({
                "payment_status": "SUCCESS",
                "via": "already_paid",
                "boost": ListingBoostSerializer(
                    boost, context={"request": request}
                ).data,
            }, status=status.HTTP_200_OK)

        # ── Free path ───────────────────────────────────────────
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
            import uuid
            with transaction.atomic():
                if not consume_credit(user=request.user, service_key="boost"):
                    return Response(
                        {"detail": "Hakuna boost credits za kutosha."},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )
                ref = f"credits-{boost.pk}-{uuid.uuid4().hex[:12]}"
                boost = mark_boost_as_paid(
                    boost=boost, payment_reference=ref,
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
            "boost": self.get_serializer(boost).data,
        }, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=None,
        responses={200: ListingBoostSerializer},
    )
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        boost = get_object_or_404(self.get_queryset(), pk=pk)
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