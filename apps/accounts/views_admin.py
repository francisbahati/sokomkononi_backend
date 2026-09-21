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


class AdminUserViewSet(viewsets.GenericViewSet):
    """
        GET     /api/admin/users/               list with filters
        GET     /api/admin/users/{id}/          retrieve
        PATCH   /api/admin/users/{id}/          partial update
        DELETE  /api/admin/users/{id}/          soft delete
        POST    /api/admin/users/{id}/suspend/
        POST    /api/admin/users/{id}/activate/
        POST    /api/admin/users/{id}/verify/
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
        for field in allowed:
            if field in data:
                setattr(user, field, data[field])
                updates.append(field)
        if updates:
            updates.append("updated_at")
            user.save(update_fields=updates)
        return Response(ProfileSerializer(user).data)

    def destroy(self, request, pk=None):
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
        user.delete(by=request.user, reason="Admin deleted")
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
        return Response({"detail": "Mtumiaji amethibitishwa."})
