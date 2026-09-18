from django.utils import timezone
from django.db.models import Q

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from .models import Lead
from .serializers import (
    LeadSerializer,
    LeadStatusUpdateSerializer,
)


class LeadViewSet(viewsets.GenericViewSet):
    """
    Seller's incoming leads. Buyers see their own sent leads.

        GET     /api/leads/                 list
        GET     /api/leads/new/             only NEW
        GET     /api/leads/new-count/       count of NEW
        GET     /api/leads/{id}/            retrieve
        POST    /api/leads/{id}/respond/    mark RESPONDED
        POST    /api/leads/{id}/convert/    mark CONVERTED
        POST    /api/leads/{id}/ignore/     mark IGNORED
        DELETE  /api/leads/{id}/            remove
    """

    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Lead.objects
            .select_related("listing", "seller", "buyer", "deal_room")
        )
        if user.is_staff:
            return qs
        return qs.filter(Q(seller=user) | Q(buyer=user))

    def list(self, request):
        qs = self.get_queryset()
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        page = self.paginate_queryset(qs)
        serializer = LeadSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        lead = self.get_object()
        return Response(LeadSerializer(lead).data)

    @action(detail=False, methods=["get"], url_path="new")
    def new(self, request):
        qs = self.get_queryset().filter(
            seller=request.user, status=Lead.Status.NEW,
        )
        page = self.paginate_queryset(qs)
        serializer = LeadSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="new-count")
    def new_count(self, request):
        count = self.get_queryset().filter(
            seller=request.user, status=Lead.Status.NEW,
        ).count()
        return Response({"count": count})

    def _transition(self, request, pk, new_status):
        lead = self.get_object()
        if lead.seller_id != request.user.id and not request.user.is_staff:
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )
        lead.status = new_status
        if new_status == Lead.Status.RESPONDED:
            lead.responded_at = timezone.now()
        elif new_status == Lead.Status.CONVERTED:
            lead.converted_at = timezone.now()
        lead.save(update_fields=[
            "status", "responded_at", "converted_at", "updated_at",
        ])
        return Response(LeadSerializer(lead).data)

    @action(detail=True, methods=["post"], url_path="respond")
    def respond(self, request, pk=None):
        return self._transition(request, pk, Lead.Status.RESPONDED)

    @action(detail=True, methods=["post"], url_path="convert")
    def convert(self, request, pk=None):
        return self._transition(request, pk, Lead.Status.CONVERTED)

    @action(detail=True, methods=["post"], url_path="ignore")
    def ignore(self, request, pk=None):
        return self._transition(request, pk, Lead.Status.IGNORED)

    def destroy(self, request, pk=None):
        lead = self.get_object()
        if lead.seller_id != request.user.id and not request.user.is_staff:
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )
        lead.delete()
        return Response(
            {"detail": "Lead imeondolewa."},
            status=status.HTTP_200_OK,
        )