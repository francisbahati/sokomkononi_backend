# apps/deals/views_admin.py
"""
Admin — Deal Rooms list with pagination.
"""
from rest_framework import permissions, viewsets
from rest_framework.response import Response

from .models import DealRoom
from .serializers_admin import AdminDealRoomSerializer


class AdminDealRoomViewSet(viewsets.GenericViewSet):
    """
    GET /api/admin/deals/           → list (paginated)
    GET /api/admin/deals/{id}/      → detail
    
    Admin anaweza kuona deals zote. Read-only.
    """
    serializer_class = AdminDealRoomSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = (
        DealRoom.objects
        .select_related(
            "listing", "listing__category", "buyer", "seller",
            "transaction", "transaction__reservation",
        )
        .prefetch_related("offers", "offers__offered_by")
        .order_by("-updated_at")
    )

    def list(self, request):
        qs = self.get_queryset()

        # Filters
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        search = request.query_params.get("search")
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(listing__title__icontains=search)
                | Q(buyer__name__icontains=search)
                | Q(seller__name__icontains=search)
            )

        page = self.paginate_queryset(qs)
        serializer = AdminDealRoomSerializer(
            page if page is not None else qs,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        obj = self.get_object()
        return Response(
            AdminDealRoomSerializer(obj, context={"request": request}).data
        )