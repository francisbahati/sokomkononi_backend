# apps/payments/views_refunds.py
"""
RefundViewSet — admin anaweza kuona na kushughulikia refunds.
"""
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsAdminUser

from .models import Refund
from .serializers import RefundSerializer
from .refunds import mark_refund_completed, mark_refund_failed


class RefundViewSet(viewsets.ModelViewSet):
    """
    GET    /api/payments/refunds/              → list (admin)
    GET    /api/payments/refunds/{id}/         → detail
    POST   /api/payments/refunds/{id}/complete/ → mark COMPLETED
    POST   /api/payments/refunds/{id}/fail/    → mark FAILED
    """
    serializer_class = RefundSerializer
    permission_classes = [IsAdminUser]
    queryset = Refund.objects.select_related("user", "processed_by")

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        promotion_type = self.request.query_params.get("promotion_type")
        if promotion_type:
            qs = qs.filter(promotion_type=promotion_type.upper())

        user_id = self.request.query_params.get("user")
        if user_id:
            qs = qs.filter(user_id=user_id)

        return qs

    def list(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = RefundSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        refund = self.get_object()
        return Response(RefundSerializer(refund).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        refund = self.get_object()
        admin_note = (request.data.get("admin_note") or "").strip()
        method = request.data.get("method")

        refund = mark_refund_completed(
            refund,
            processed_by=request.user,
            admin_note=admin_note,
            method=method,
        )

        return Response(RefundSerializer(refund).data)

    @action(detail=True, methods=["post"], url_path="fail")
    def fail(self, request, pk=None):
        refund = self.get_object()
        admin_note = (request.data.get("admin_note") or "").strip()

        refund = mark_refund_failed(refund, admin_note=admin_note)

        return Response(RefundSerializer(refund).data)