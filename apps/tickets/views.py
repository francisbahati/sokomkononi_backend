import secrets

from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from apps.accounts.models import User

from .models import Ticket, TicketMessage
from .serializers import (
    TicketAssignSerializer,
    TicketCreateSerializer,
    TicketMessageCreateSerializer,
    TicketMessageSerializer,
    TicketPrioritySerializer,
    TicketSerializer,
    TicketStatusSerializer,
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


def generate_ticket_code():
    return f"TKT-{secrets.token_hex(5).upper()}"


class TicketViewSet(viewsets.GenericViewSet):
    """
        GET     /api/tickets/                      admin: all, user: own
        GET     /api/tickets/{id}/
        POST    /api/tickets/                      create
        POST    /api/tickets/{id}/messages/        add message
        POST    /api/tickets/{id}/status/          admin only
        POST    /api/tickets/{id}/priority/        admin only
        POST    /api/tickets/{id}/assign/          admin only
        DELETE  /api/tickets/{id}/                 admin or owner
    """

    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Ticket.objects.select_related("user", "assigned_to").prefetch_related("messages")
        if user.is_staff:
            return qs
        return qs.filter(user=user)

    def list(self, request):
        qs = self.get_queryset()
        status_filter = request.query_params.get("status")
        category_filter = request.query_params.get("category")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if category_filter:
            qs = qs.filter(category=category_filter.upper())
        page = self.paginate_queryset(qs)
        serializer = TicketSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(TicketSerializer(obj).data)

    @extend_schema(
        request=TicketCreateSerializer,
        responses={201: TicketSerializer},
    )
    def create(self, request):
        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Ensure unique code
        code = generate_ticket_code()
        while Ticket.objects.filter(code=code).exists():
            code = generate_ticket_code()

        ticket = Ticket.objects.create(
            code=code,
            subject=data["subject"],
            description=data.get("description", ""),
            category=data["category"],
            priority=data["priority"],
            user=request.user,
            user_name=request.user.name,
            user_email=request.user.email or "",
        )

        if data.get("description"):
            TicketMessage.objects.create(
                ticket=ticket,
                sender=TicketMessage.Sender.USER,
                sender_name=request.user.name,
                text=data["description"],
            )

        return Response(
            TicketSerializer(ticket).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=TicketMessageCreateSerializer,
        responses={201: TicketMessageSerializer},
    )
    @action(detail=True, methods=["post"], url_path="messages")
    def add_message(self, request, pk=None):
        ticket = get_object_or_404(self.get_queryset(), pk=pk)
        if ticket.status == Ticket.Status.CLOSED and not request.user.is_staff:
            return Response(
                {"detail": "Ticket imefungwa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = TicketMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sender = (
            TicketMessage.Sender.ADMIN
            if request.user.is_staff
            else TicketMessage.Sender.USER
        )
        msg = TicketMessage.objects.create(
            ticket=ticket,
            sender=sender,
            sender_name=request.user.name,
            text=serializer.validated_data["text"],
        )
        ticket.save(update_fields=["updated_at"])
        return Response(
            TicketMessageSerializer(msg).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=TicketStatusSerializer,
        responses={200: TicketSerializer},
    )
    @action(detail=True, methods=["post"], url_path="status",
            permission_classes=[IsAdminUser])
    def set_status(self, request, pk=None):
        ticket = get_object_or_404(Ticket, pk=pk)
        serializer = TicketStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket.status = serializer.validated_data["status"]
        if ticket.status == Ticket.Status.RESOLVED and not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        ticket.save(update_fields=["status", "resolved_at", "updated_at"])
        return Response(TicketSerializer(ticket).data)

    @extend_schema(
        request=TicketPrioritySerializer,
        responses={200: TicketSerializer},
    )
    @action(detail=True, methods=["post"], url_path="priority",
            permission_classes=[IsAdminUser])
    def set_priority(self, request, pk=None):
        ticket = get_object_or_404(Ticket, pk=pk)
        serializer = TicketPrioritySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket.priority = serializer.validated_data["priority"]
        ticket.save(update_fields=["priority", "updated_at"])
        return Response(TicketSerializer(ticket).data)

    @extend_schema(
        request=TicketAssignSerializer,
        responses={200: TicketSerializer},
    )
    @action(detail=True, methods=["post"], url_path="assign",
            permission_classes=[IsAdminUser])
    def assign(self, request, pk=None):
        ticket = get_object_or_404(Ticket, pk=pk)
        serializer = TicketAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = get_object_or_404(
            User, pk=serializer.validated_data["staff_id"], is_staff=True,
        )
        ticket.assigned_to = staff
        ticket.assigned_to_name = staff.name
        ticket.save(update_fields=[
            "assigned_to", "assigned_to_name", "updated_at",
        ])
        return Response(TicketSerializer(ticket).data)

    def destroy(self, request, pk=None):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        if obj.user_id != request.user.id and not request.user.is_staff:
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)