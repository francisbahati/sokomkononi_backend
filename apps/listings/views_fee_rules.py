from django.db import IntegrityError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status as drf_status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteViewSetMixin

from .models import ListingFeeRule
from .serializers_fee_rules import ListingFeeRuleSerializer


class FeeRulePagination(PageNumberPagination):
    """
    Frontend inaomba /fee-rules/?page_size=200. Bila page_size_query_param,
    DRF inapuuza parameter hiyo na kurudisha rules 20 tu — rules za
    kategoria mpya (zilizo mwishoni) hazionekani, na kujaribu kuziongeza
    kunaleta 400 DUPLICATE_ACTIVE_RULE.
    """
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )

def _log(request, action, target="", target_id=None, details=""):
    try:
        from apps.audit.services.audit import log_action
        log_action(
            request=request,
            action=action,
            target=target,
            target_id=target_id,
            details=details,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to write audit log: %s", action,
        )

class ListingFeeRuleViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ListingFeeRuleSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = FeeRulePagination
    staff_can_restore_any = True

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["category", "is_active", "is_deleted"]

    def get_queryset(self):
        qs = ListingFeeRule.objects.all()
        if (
            self.request.user.is_authenticated
            and self.request.user.is_staff
        ):
            return qs.order_by("priority", "min_price", "id")
        return qs.filter(is_active=True).order_by("priority", "min_price", "id")

    def _can_restore(self, instance):
        return bool(
            self.request.user.is_authenticated
            and self.request.user.is_staff
        )

    # ── CREATE ──────────────────────────────────────────────
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            self.perform_create(serializer)
        except IntegrityError as exc:
            msg = str(exc)
            if "unique_active_rule_per_category" in msg:
                return Response(
                    {
                        "detail": (
                            "Kuna kanuni ya ada (fee rule) tayari inatumika "
                            "kwa category hii. Zima au futa ile ya zamani kwanza, "
                            "kisha uunde mpya."
                        ),
                        "code": "DUPLICATE_ACTIVE_RULE",
                    },
                    status=drf_status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"detail": "Imeshindwa kuunda fee rule."},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        response = Response(serializer.data, status=drf_status.HTTP_201_CREATED)
        headers = self.get_success_headers(serializer.data)
        response.headers.update(headers)

        data = response.data or {}
        name = (
            data.get("name")
            or data.get("category_slug")
            or data.get("category")
            or "—"
        )
        _log(
            request,
            action="fee.created",
            target="ListingFeeRule",
            target_id=data.get("id"),
            details=f"Created listing fee rule: {name}",
        )

        return response

    # ── UPDATE / PARTIAL_UPDATE ─────────────────────────────
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_snapshot = self._snapshot(instance)

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=kwargs.pop("partial", False),
        )
        serializer.is_valid(raise_exception=True)

        try:
            self.perform_update(serializer)
        except IntegrityError as exc:
            msg = str(exc)
            if "unique_active_rule_per_category" in msg:
                return Response(
                    {
                        "detail": (
                            "Kuna kanuni ya ada (fee rule) tayari inatumika "
                            "kwa category hii. Zima au futa ile ya zamani kwanza."
                        ),
                        "code": "DUPLICATE_ACTIVE_RULE",
                    },
                    status=drf_status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"detail": "Imeshindwa kusasisha fee rule."},
                status=drf_status.HTTP_400_BAD_REQUEST,
            )

        instance.refresh_from_db()
        diff = self._diff(old_snapshot, self._snapshot(instance))
        _log(
            request,
            action="fee.updated",
            target="ListingFeeRule",
            target_id=instance.id,
            details=(
                f"Updated listing fee rule: "
                f"{instance.name or instance.category_slug or '—'} "
                f"({diff})"
            ),
        )

        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    # ── DESTROY ─────────────────────────────────────────────
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        rule_id = instance.id
        rule_name = (
            instance.name
            or instance.category_slug
            or getattr(instance, "category_id", None)
            or "—"
        )

        response = super().destroy(request, *args, **kwargs)

        if response.status_code in (
            drf_status.HTTP_204_NO_CONTENT,
            drf_status.HTTP_200_OK,
        ):
            _log(
                request,
                action="fee.deleted",
                target="ListingFeeRule",
                target_id=rule_id,
                details=f"Deleted listing fee rule: {rule_name}",
            )

        return response

    # ── HELPERS ─────────────────────────────────────────────
    @staticmethod
    def _snapshot(instance):
        return {
            "fee_mode": getattr(instance, "fee_mode", None),
            "flat_fee": str(getattr(instance, "flat_fee", "") or ""),
            "percentage": str(getattr(instance, "percentage", "") or ""),
            "min_price": str(getattr(instance, "min_price", "") or ""),
            "max_price": str(getattr(instance, "max_price", "") or ""),
            "is_active": bool(getattr(instance, "is_active", True)),
        }

    @staticmethod
    def _diff(old, new):
        changes = []
        for key in old:
            if old[key] != new[key]:
                changes.append(f"{key}: {old[key]} → {new[key]}")
        return ", ".join(changes) if changes else "no change"