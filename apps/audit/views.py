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


from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.GenericViewSet):
    """
        GET     /api/audit/                   admin: list
        GET     /api/audit/{id}/
        DELETE  /api/audit/{id}/
        POST    /api/audit/clear/             wipe all
    """

    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("admin_user")
        action_filter = self.request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter)
        return qs

    def list(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = AuditLogSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        obj = self.get_object()
        return Response(AuditLogSerializer(obj).data)

    def destroy(self, request, pk=None):
        obj = self.get_object()
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="clear")
    def clear(self, request):
        AuditLog.objects.all().delete()
        return Response({"detail": "Kumbukumbu zote zimefutwa."})