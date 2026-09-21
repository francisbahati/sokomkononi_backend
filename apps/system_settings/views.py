from django.shortcuts import get_object_or_404

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


from apps.accounts.models import User
from apps.rbac.models import Role, StaffAssignment
from apps.rbac.serializers import StaffAssignmentSerializer

from .models import AppStoreLinks, PlatformPolicy, Webhook
from .serializers import (
    AppStoreLinksSerializer,
    PlatformPolicySerializer,
    WebhookSerializer,
)


class WebhookViewSet(viewsets.GenericViewSet):
    serializer_class = WebhookSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return Webhook.objects.all()

    def list(self, request):
        return Response(WebhookSerializer(self.get_queryset(), many=True).data)

    def create(self, request):
        serializer = WebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="toggle")
    def toggle(self, request, pk=None):
        obj = self.get_object()
        obj.active = not obj.active
        obj.save(update_fields=["active"])
        return Response(WebhookSerializer(obj).data)

    def destroy(self, request, pk=None):
        obj = self.get_object()
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AppStoreLinksView(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    def list(self, request):
        obj, _ = AppStoreLinks.objects.get_or_create(pk=1)
        return Response(AppStoreLinksSerializer(obj).data)

    def create(self, request):
        obj, _ = AppStoreLinks.objects.get_or_create(pk=1)
        serializer = AppStoreLinksSerializer(
            obj, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class PlatformPolicyView(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    def list(self, request):
        obj, _ = PlatformPolicy.objects.get_or_create(pk=1)
        return Response(PlatformPolicySerializer(obj).data)

    def create(self, request):
        obj, _ = PlatformPolicy.objects.get_or_create(pk=1)
        serializer = PlatformPolicySerializer(
            obj, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class SubAdminViewSet(viewsets.GenericViewSet):
    """
        GET     /api/system-settings/sub-admins/           list
        POST    /api/system-settings/sub-admins/           create
        DELETE  /api/system-settings/sub-admins/{id}/      remove
    """

    serializer_class = StaffAssignmentSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return StaffAssignment.objects.select_related("user", "role")

    def list(self, request):
        return Response(
            StaffAssignmentSerializer(self.get_queryset(), many=True).data,
        )

    def create(self, request):
        data = request.data or {}
        user_id = data.get("user_id") or data.get("user")
        role_key = data.get("role_key") or data.get("role")

        if not user_id or not role_key:
            return Response(
                {"detail": "user_id na role_key zinahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = get_object_or_404(User, pk=user_id)
        role = get_object_or_404(Role, key=role_key)

        # Make sure the user is flagged as staff so IsAdminUser works.
        if not user.is_staff:
            user.is_staff = True
            user.save(update_fields=["is_staff", "updated_at"])

        obj, _ = StaffAssignment.objects.update_or_create(
            user=user,
            defaults={
                "role": role,
                "active": data.get("active", True),
            },
        )
        return Response(
            StaffAssignmentSerializer(obj).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, pk=None):
        obj = get_object_or_404(StaffAssignment, pk=pk)
        user = obj.user
        obj.delete()
        # Optionally revoke staff status if no other assignment remains.
        if not StaffAssignment.objects.filter(user=user).exists():
            user.is_staff = False
            user.save(update_fields=["is_staff", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
