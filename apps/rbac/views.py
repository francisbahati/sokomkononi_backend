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

        key = d["key"]
        if Role.objects.filter(key=key).exists():
            return Response(
                {"detail": "Role hii ipo tayari."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        obj = Role.objects.create(
            key=key,
            label_sw=d.get("label_sw") or "",
            label_en=d.get("label_en") or "",
            description_sw=d.get("description_sw") or "",
            description_en=d.get("description_en") or "",
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
        if "label_sw" in d:
            obj.label_sw = d["label_sw"] or ""
        if "label_en" in d:
            obj.label_en = d["label_en"] or ""
        if "description_sw" in d:
            obj.description_sw = d["description_sw"] or ""
        if "description_en" in d:
            obj.description_en = d["description_en"] or ""
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
        # Grant admin access on assignment.
        if not user.is_staff:
            user.is_staff = True
            user.save(update_fields=["is_staff", "updated_at"])
        return Response(
            StaffAssignmentSerializer(obj).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, pk=None):
        obj = get_object_or_404(StaffAssignment, pk=pk)
        data = request.data or {}
        if "role_key" in data:
            role = Role.objects.filter(key=data["role_key"]).first()
            if not role:
                return Response(
                    {"detail": "Role haipatikani."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            obj.role = role
        if "active" in data:
            obj.active = bool(data["active"])
        obj.save()
        return Response(StaffAssignmentSerializer(obj).data)

    def destroy(self, request, pk=None):
        obj = get_object_or_404(StaffAssignment, pk=pk)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
