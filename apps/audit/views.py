from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.GenericViewSet):
    """
        GET /api/audit/            staff: list (read-only)
        GET /api/audit/{id}/       staff: retrieve

    Deletion and clearing are DELIBERATELY DISABLED via the API.
    Audit logs are append-only. Use Django admin (superuser) if you
    absolutely must intervene, and note that intervention elsewhere.
    """

    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAdminUser]
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("admin_user")
        action_filter = self.request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter)
        return qs

    def list(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = AuditLogSerializer(page if page is not None else qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        obj = self.get_object()
        return Response(AuditLogSerializer(obj).data)
