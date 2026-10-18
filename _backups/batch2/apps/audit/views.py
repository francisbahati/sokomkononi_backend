# apps/audit/views.py

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AuditLog
from .serializers import AuditLogSerializer


class IsSuperUser(permissions.BasePermission):
    """Kufuta logs — superuser pekee."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )


class AuditLogViewSet(viewsets.GenericViewSet):
    """
        GET    /api/audit/             staff: list (read-only)
        GET    /api/audit/{id}/        staff: retrieve (full detail)
        DELETE /api/audit/{id}/        superuser: delete one log
        POST   /api/audit/clear/       superuser: delete ALL logs
    """

    serializer_class = AuditLogSerializer

    def get_permissions(self):
        if self.action in ("destroy", "clear"):
            return [IsSuperUser()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("admin_user")
        action_filter = self.request.query_params.get("action")
        if action_filter:
            qs = qs.filter(action=action_filter)
        admin_filter = self.request.query_params.get("admin_user")
        if admin_filter:
            qs = qs.filter(admin_user_id=admin_filter)
        search = self.request.query_params.get("search")
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(admin_name__icontains=search)
                | Q(target__icontains=search)
                | Q(details__icontains=search)
                | Q(action__icontains=search)
            )
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

    # ------------------------------------------------------------
    # DELETE — moja moja (superuser pekee)
    # ------------------------------------------------------------
    def destroy(self, request, pk=None):
        obj = self.get_object()
        obj_id = obj.id
        obj_action = obj.action
        obj_admin = obj.admin_name

        obj.delete()

        # Andika audit log mpya kuhusu kufutwa huku (append-only)
        try:
            from .services.audit import log_action
            log_action(
                request=request,
                action="audit.deleted",
                target="AuditLog",
                target_id=obj_id,
                details=f"Deleted log: action={obj_action} admin={obj_admin}",
            )
        except Exception:
            pass

        return Response(status=status.HTTP_204_NO_CONTENT)

    # ------------------------------------------------------------
    # CLEAR — zote (superuser pekee)
    # ------------------------------------------------------------
    @action(
        detail=False,
        methods=["post"],
        url_path="clear",
        permission_classes=[IsSuperUser],
    )
    def clear(self, request):
        count = AuditLog.objects.count()
        AuditLog.objects.all().delete()

        # Andika audit log mpya
        try:
            from .services.audit import log_action
            log_action(
                request=request,
                action="audit.cleared",
                target="AuditLog",
                target_id=None,
                details=f"Cleared {count} audit logs.",
            )
        except Exception:
            pass

        return Response({
            "deleted": count,
            "detail": f"Logs {count} zimefutwa.",
        })