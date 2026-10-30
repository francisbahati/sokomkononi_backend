# ============================================================
# apps/accounts/views_admin.py
# Admin user management — list, retrieve, patch, soft delete,
# suspend, activate, verify, permanent delete.
# ============================================================
import logging

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import User
from .serializers import AdminUserSerializer
from .services import get_user_role


logger = logging.getLogger(__name__)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class AdminUserPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ✅ Ongeza params=None kwenye signature
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
        logger.exception("Failed to write audit log: %s", action)


class AdminUserViewSet(viewsets.GenericViewSet):
    """
        GET     /api/admin/users/               list with filters
        GET     /api/admin/users/{id}/          retrieve
        PATCH   /api/admin/users/{id}/          partial update
        DELETE  /api/admin/users/{id}/          soft delete
        POST    /api/admin/users/{id}/suspend/
        POST    /api/admin/users/{id}/activate/
        POST    /api/admin/users/{id}/verify/
        DELETE  /api/admin/users/{id}/permanent/  hard delete (HAIRUDISHWI)
    """

    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]
    pagination_class = AdminUserPagination

    def get_queryset(self):
        from django.db.models import Exists, OuterRef, Q as DQ
        from apps.listings.models import Listing
        from apps.deals.models import DealRoom
        from apps.verifications.models import VerificationRequest

        qs = User.all_objects.all().order_by("-created_at")

        has_listings = Listing.objects.filter(
            seller=OuterRef("pk"), is_deleted=False,
        )
        has_deals = DealRoom.objects.filter(buyer=OuterRef("pk"))

        has_verified = VerificationRequest.objects.filter(
            user=OuterRef("pk"),
            status=VerificationRequest.Status.APPROVED,
        )

        qs = qs.annotate(
            _has_listings=Exists(has_listings),
            _has_deals=Exists(has_deals),
            _has_verified=Exists(has_verified),
        )

        q = self.request.query_params.get("q")
        role = self.request.query_params.get("role")
        status_filter = self.request.query_params.get("status")
        verified_filter = self.request.query_params.get("verified")

        if q:
            qs = qs.filter(
                DQ(name__icontains=q)
                | DQ(email__icontains=q)
                | DQ(phone__icontains=q)
            )

        if role and role.lower() != "all":
            target = role.lower()
            if target == "admin":
                qs = qs.filter(DQ(is_staff=True) | DQ(is_superuser=True))
            elif target == "seller":
                qs = qs.filter(_has_listings=True, _has_deals=False)
            elif target == "buyer":
                qs = qs.filter(_has_listings=False, _has_deals=True)
            elif target == "both":
                qs = qs.filter(_has_listings=True, _has_deals=True)
            elif target == "neither":
                qs = qs.filter(_has_listings=False, _has_deals=False)

        if status_filter == "active":
            qs = qs.filter(is_active=True)
        elif status_filter == "suspended":
            qs = qs.filter(is_active=False)

        if verified_filter == "verified":
            qs = qs.filter(_has_verified=True)
        elif verified_filter == "unverified":
            qs = qs.filter(_has_verified=False)

        return qs

    def _get_user(self, pk):
        return User.all_objects.filter(pk=pk).first()

    def list(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = AdminUserSerializer(
            page if page is not None else qs,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = self._get_user(pk)
        if not user:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            AdminUserSerializer(user, context={"request": request}).data
        )

    def partial_update(self, request, pk=None):
        user = self._get_user(pk)
        if not user:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = request.data or {}
        allowed = {
            "name", "phone", "account_type",
            "is_active", "is_verified", "is_staff",
        }
        updates = []
        changed_fields = []
        for field in allowed:
            if field in data:
                old_value = getattr(user, field, None)
                new_value = data[field]
                if old_value != new_value:
                    changed_fields.append(field)
                setattr(user, field, new_value)
                updates.append(field)
        if updates:
            updates.append("updated_at")
            user.save(update_fields=updates)

            # ✅ Tumia params
            _log(
                request,
                action="user.updated",
                target="User",
                target_id=user.id,
                params={
                    "name": f"{user.name} ({user.email or user.deleted_email or '—'})",
                    "fields": ", ".join(changed_fields) or "—",
                },
            )

        return Response(
            AdminUserSerializer(user, context={"request": request}).data
        )

    def destroy(self, request, pk=None):
        """Soft delete — inaweka kwenye kikapu (is_deleted=True)."""
        user = self._get_user(pk)
        if not user:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if user.id == request.user.id:
            return Response(
                {"detail": "Huwezi kujifuta mwenyewe."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user_name = user.name
        user_email = user.email or user.deleted_email or "—"
        user.delete(by=request.user, reason="Admin deleted")

        # ✅ Tumia params
        _log(
            request,
            action="user.deleted",
            target="User",
            target_id=user.id,
            params={"name": f"{user_name} ({user_email})"},
        )

        return Response(
            {"detail": "Mtumiaji amewekwa kwenye kikapu."},
            status=status.HTTP_200_OK,
        )

    # ========================================================
    # SUSPEND — inahitaji sababu
    # ========================================================
    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, pk=None):
        user = self._get_user(pk)
        if not user:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_staff or user.is_superuser:
            return Response(
                {"detail": "Hauwezi kumsimamisha admin."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.id == request.user.id:
            return Response(
                {"detail": "Huwezi kujisimamisha mwenyewe."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = (request.data.get("reason") or "").strip()
        if len(reason) < 5:
            return Response(
                {"detail": "Sababu ya kusimamisha inahitajika (herufi 5+)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])

        # ── Email ───────────────────────────────────────────
        try:
            from apps.accounts.email_service import send_account_suspended_email
            send_account_suspended_email(
                to_email=user.email or user.deleted_email,
                name=user.name,
                reason=reason,
            )
        except Exception:
            logger.exception("Failed to send suspension email to %s", user.id)

        # ✅ Tumia params
        _log(
            request,
            action="user.suspended",
            target="User",
            target_id=user.id,
            params={
                "name": f"{user.name} ({user.email or '—'})",
                "reason": reason,
            },
        )

        return Response({"detail": "Mtumiaji amesimamishwa."})

    # ========================================================
    # ACTIVATE
    # ========================================================
    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        user = self._get_user(pk)
        if not user:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])

        # ✅ Tumia params
        _log(
            request,
            action="user.activated",
            target="User",
            target_id=user.id,
            params={"name": f"{user.name} ({user.email or '—'})"},
        )

        return Response({"detail": "Mtumiaji amewashwa."})

    # ========================================================
    # VERIFY
    # ========================================================
    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        user = self._get_user(pk)
        if not user:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        user.is_verified = True
        user.save(update_fields=["is_verified", "updated_at"])

        # ✅ Tumia params
        _log(
            request,
            action="user.verified",
            target="User",
            target_id=user.id,
            params={"name": f"{user.name} ({user.email or '—'})"},
        )

        return Response({"detail": "Mtumiaji amethibitishwa."})

    # ========================================================
    # PERMANENT DELETE — inahitaji reason + confirm_text
    # ========================================================
    @action(
        detail=True,
        methods=["delete"],
        url_path="permanent",
        url_name="permanent-delete",
    )
    def permanent_delete(self, request, pk=None):
        """
        Hard delete user — HAIRUDISHWI.
        """
        user = self._get_user(pk)
        if not user:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_staff or user.is_superuser:
            return Response(
                {"detail": "Hauwezi kumfuta admin. Wasiliana na Super Admin."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.id == request.user.id:
            return Response(
                {"detail": "Huwezi kujifuta mwenyewe."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data or {}
        reason = (data.get("reason") or "").strip()
        confirm_text = (data.get("confirm_text") or "").strip()

        if len(reason) < 5:
            return Response(
                {"detail": "Sababu ya kufuta inahitajika (herufi 5+)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if confirm_text != "DELETE":
            return Response(
                {"detail": 'Lazima uandike "DELETE" kuthibitisha.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_id = user.id
        user_email = user.email or user.deleted_email or "—"
        user_name = user.name

        try:
            from apps.accounts.email_service import send_account_deleted_email
            send_account_deleted_email(
                to_email=user_email if user_email != "—" else None,
                name=user_name,
                reason=reason,
            )
        except Exception:
            logger.exception("Failed to send deletion email to %s", user_id)

        try:
            user.hard_delete()
        except AttributeError:
            user.delete(by=request.user, reason=reason)

        # ✅ Tumia params
        _log(
            request,
            action="user.permanent_deleted",
            target="User",
            target_id=user_id,
            params={"name": f"{user_name} ({user_email})", "reason": reason},
        )

        return Response(
            {
                "detail": f"Mtumiaji {user_name} amefutwa kabisa.",
                "deleted_id": user_id,
            },
            status=status.HTTP_200_OK,
        )