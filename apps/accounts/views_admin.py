from django.db.models import Q

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import User
from .serializers import ProfileSerializer


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


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

    serializer_class = ProfileSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = User.all_objects.all().order_by("-created_at")
        q = self.request.query_params.get("q")
        role = self.request.query_params.get("role")
        status_filter = self.request.query_params.get("status")

        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
            )
        if role == "Buyer":
            qs = qs.filter(is_staff=False)
        elif role == "Seller":
            qs = qs.filter(is_staff=False)
        if status_filter == "active":
            qs = qs.filter(is_active=True)
        elif status_filter == "suspended":
            qs = qs.filter(is_active=False)
        return qs

    def _get_user(self, pk):
        return User.all_objects.filter(pk=pk).first()

    def list(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = ProfileSerializer(
            page if page is not None else qs, many=True,
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
        return Response(ProfileSerializer(user).data)

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

            _log(
                request,
                action="user.updated",
                target="User",
                target_id=user.id,
                details=(
                    f"Updated {user.name} "
                    f"({user.email or user.deleted_email or '—'}): "
                    f"fields={', '.join(changed_fields) or 'none'}"
                ),
            )

        return Response(ProfileSerializer(user).data)

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

        _log(
            request,
            action="user.deleted",
            target="User",
            target_id=user.id,
            details=f"Soft-deleted user: {user_name} ({user_email})",
        )

        return Response(
            {"detail": "Mtumiaji amewekwa kwenye kikapu."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="suspend")
    def suspend(self, request, pk=None):
        user = self._get_user(pk)
        if not user:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])

        _log(
            request,
            action="user.suspended",
            target="User",
            target_id=user.id,
            details=f"Suspended user: {user.name} ({user.email or '—'})",
        )

        return Response({"detail": "Mtumiaji amesimamishwa."})

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

        _log(
            request,
            action="user.activated",
            target="User",
            target_id=user.id,
            details=f"Activated user: {user.name} ({user.email or '—'})",
        )

        return Response({"detail": "Mtumiaji amewashwa."})

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

        _log(
            request,
            action="user.verified",
            target="User",
            target_id=user.id,
            details=f"Verified user: {user.name} ({user.email or '—'})",
        )

        return Response({"detail": "Mtumiaji amethibitishwa."})

    @action(
        detail=True,
        methods=["delete"],
        url_path="permanent",
        url_name="permanent-delete",
    )
    def permanent_delete(self, request, pk=None):
        """
        Hard delete user — HAIRUDISHWI.

        - Admin pekee
        - Hauwezi kumfuta admin / superuser mwingine
        - Hauwezi kujifuta mwenyewe

        Endpoint: DELETE /api/admin/users/{id}/permanent/
        """
        user = self._get_user(pk)
        if not user:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_staff or user.is_superuser:
            return Response(
                {
                    "detail": (
                        "Hauwezi kumfuta admin. "
                        "Wasiliana na Super Admin."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.id == request.user.id:
            return Response(
                {"detail": "Hauwezi kujifuta mwenyewe."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user_id = user.id
        user_email = user.email or user.deleted_email or "—"
        user_name = user.name

        try:
            user.hard_delete()
        except AttributeError:
            user.delete(
                by=request.user,
                reason="Admin permanent delete (fallback)",
            )

        _log(
            request,
            action="user.permanent_deleted",
            target="User",
            target_id=user_id,
            details=f"Permanently deleted user: {user_name} ({user_email})",
        )

        return Response(
            {
                "detail": (
                    f"Mtumiaji {user_name} ({user_email}) "
                    f"amefutwa kabisa."
                ),
                "deleted_id": user_id,
            },
            status=status.HTTP_200_OK,
        )