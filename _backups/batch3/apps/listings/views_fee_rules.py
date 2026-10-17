from rest_framework import permissions, viewsets

from apps.core.mixins import SoftDeleteViewSetMixin

from .models import ListingFeeRule
from .serializers_fee_rules import ListingFeeRuleSerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


# ============================================================
# AUDIT LOG HELPER
# ============================================================
def _log(request, action, target="", target_id=None, details=""):
    """Helper — ina-logi admin action bila kuvunja request kama log inashindwa."""
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
    staff_can_restore_any = True

    def get_queryset(self):
        qs = ListingFeeRule.objects.all()
        if (
            self.request.user.is_authenticated
            and self.request.user.is_staff
        ):
            return qs.order_by("priority", "min_price")
        return qs.filter(is_active=True).order_by("priority", "min_price")

    def _can_restore(self, instance):
        return bool(
            self.request.user.is_authenticated
            and self.request.user.is_staff
        )

    # ══════════════════════════════════════════════════════════
    # CREATE — log fee.created
    # ══════════════════════════════════════════════════════════
    def create(self, request, *args, **kwargs):
        from rest_framework import status as drf_status
        response = super().create(request, *args, **kwargs)

        if response.status_code == drf_status.HTTP_201_CREATED:
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

    # ══════════════════════════════════════════════════════════
    # UPDATE / PARTIAL_UPDATE — log fee.updated
    # ══════════════════════════════════════════════════════════
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_snapshot = self._snapshot(instance)

        response = super().update(request, *args, **kwargs)

        from rest_framework import status as drf_status
        if response.status_code in (
            drf_status.HTTP_200_OK,
            drf_status.HTTP_202_ACCEPTED,
        ):
            # `super().update()` inapakia kitu chake kipya kutoka database,
            # kwa hiyo `instance` yetu ni ya zamani — i-refresh la sivyo
            # diff itasema "no change" kila mara.
            try:
                instance.refresh_from_db()
                diff = self._diff(old_snapshot, self._snapshot(instance))
            except Exception:
                diff = "diff haipatikani"
            _log(
                request,
                action="fee.updated",
                target="ListingFeeRule",
                target_id=instance.id,
                details=(
                    f"Updated listing fee rule: {instance.name or instance.category_slug or '—'} "
                    f"({diff})"
                ),
            )

        return response

    def partial_update(self, request, *args, **kwargs):
        # MUHIMU: PATCH lazima iwe `partial=True`. DRF inaiweka hivi kwa
        # default; kuiandika upya bila hiyo kunafanya serializer idai fields
        # ZOTE zinazohitajika, kwa hiyo toggle ya `is_active` peke yake
        # inarudi 400 Bad Request.
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    # ══════════════════════════════════════════════════════════
    # DESTROY — log fee.deleted
    # ══════════════════════════════════════════════════════════
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

        from rest_framework import status as drf_status
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

    # ══════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════
    @staticmethod
    def _snapshot(instance):
        """Chukua snapshot ya fields za fee kwa diff."""
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
        """Rudisha mabadiliko kama string fupi."""
        changes = []
        for key in old:
            if old[key] != new[key]:
                changes.append(f"{key}: {old[key]} → {new[key]}")
        return ", ".join(changes) if changes else "no change"