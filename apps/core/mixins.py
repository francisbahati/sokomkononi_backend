from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response


class SoftDeleteViewSetMixin:
    """
    Drop-in mixin for DRF viewsets backed by a SoftDeleteModel.

    Adds:
        DELETE  -> soft delete
        POST  .../<pk>/restore/  -> restore
        GET   .../trash/         -> list of deleted rows (staff only)
    """

    #: set to True on viewsets where staff-only can restore other users' rows
    staff_can_restore_any = True

    def perform_destroy(self, instance):
        reason = ""
        if hasattr(self.request, "data") and isinstance(self.request.data, dict):
            reason = self.request.data.get("reason", "")
        instance.delete(by=self.request.user, reason=reason)

    def _can_restore(self, instance):
        user = self.request.user
        if user.is_staff and self.staff_can_restore_any:
            return True
        owner_field = getattr(self, "owner_field", "seller")
        owner_id = getattr(instance, f"{owner_field}_id", None)
        return owner_id == user.id

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        instance = self.get_queryset_with_deleted().get(pk=pk)

        if not self._can_restore(instance):
            raise PermissionDenied(
                "Huna ruhusa ya kurejesha kitu hiki."
            )

        instance.restore()
        return Response(
            self.get_serializer(instance).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="trash")
    def trash(self, request):
        if not request.user.is_staff:
            raise PermissionDenied(
                "Ni wasimamizi pekee wanaoweza kuona kikapu."
            )

        qs = self.get_queryset_with_deleted().filter(is_deleted=True)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(
            page if page is not None else qs,
            many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def get_queryset_with_deleted(self):
        model = self.get_queryset().model
        return model.all_objects.all()