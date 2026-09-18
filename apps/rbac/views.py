from django.shortcuts import get_object_or_404

from rest_framework import permissions, status, viewsets
from rest_framework.response import Response


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


from apps.accounts.models import User

from .models import Role, StaffAssignment
from .serializers import (
    RoleSerializer,
    StaffAssignmentSerializer,
    StaffCreateSerializer,
)


class RoleViewSet(viewsets.GenericViewSet):
    """
        GET     /api/rbac/roles/
        POST    /api/rbac/roles/
        PATCH   /api/rbac/roles/{id}/
        DELETE  /api/rbac/roles/{id}/     (non-system only)
    """

    serializer_class = RoleSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return Role.objects.all()

    def list(self, request):
        qs = self.get_queryset()
        return Response(RoleSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        obj = get_object_or_404(Role, pk=pk)
        return Response(RoleSerializer(obj).data)

    def create(self, request):
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        label = d.get("label") or {}
        description = d.get("description") or {}

        key = d["key"]
        if Role.objects.filter(key=key).exists():
            return Response(
                {"detail": "Role hii ipo tayari."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        obj = Role.objects.create(
            key=key,
            label_sw=label.get("sw", ""),
            label_en=label.get("en", ""),
            description_sw=description.get("sw", ""),
            description_en=description.get("en", ""),
            permissions=d.get("permissions", []),
            is_system=False,
        )
        return Response(
            RoleSerializer(obj).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, pk=None):
        obj = get_object_or_404(Role, pk=pk)
        serializer = RoleSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        if "label" in d:
            label = d["label"] or {}
            obj.label_sw = label.get("sw", "")
            obj.label_en = label.get("en", "")
        if "description" in d:
            description = d["description"] or {}
            obj.description_sw = description.get("sw", "")
            obj.description_en = description.get("en", "")
        if "permissions" in d:
            obj.permissions = d["permissions"]
        obj.save()
        return Response(RoleSerializer(obj).data)

    def destroy(self, request, pk=None):
        obj = get_object_or_404(Role, pk=pk)
        if obj.is_system:
            return Response(
                {"detail": "Role za mfumo haziwezi kufutwa."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffViewSet(viewsets.GenericViewSet):
    """
        GET     /api/rbac/staff/
        POST    /api/rbac/staff/
        PATCH   /api/rbac/staff/{id}/
        DELETE  /api/rbac/staff/{id}/
    """

    serializer_class = StaffAssignmentSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return StaffAssignment.objects.select_related("user", "role")

    def list(self, request):
        qs = self.get_queryset()
        return Response(StaffAssignmentSerializer(qs, many=True).data)

    def create(self, request):
        serializer = StaffCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        user = get_object_or_404(User, pk=d["user_id"])
        role = get_object_or_404(Role, key=d["role_key"])

        obj, _ = StaffAssignment.objects.update_or_create(
            user=user,
            defaults={"role": role, "active": d.get("active", True)},
        )
        return Response(
            StaffAssignmentSerializer(obj).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, pk=None):
        obj = get_object_or_404(StaffAssignment, pk=pk)
        data = request.data or {}
        if "role_key" in data:
            obj.role = get_object_or_404(Role, key=data["role_key"])
        if "active" in data:
            obj.active = bool(data["active"])
        obj.save()
        return Response(StaffAssignmentSerializer(obj).data)

    def destroy(self, request, pk=None):
        obj = get_object_or_404(StaffAssignment, pk=pk)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)