import logging
import secrets

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone

from datetime import timedelta

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from apps.accounts.models import User
from apps.audit.services.audit import log_action

from .models import Ticket, TicketAttachment, TicketMessage
from .serializers import (
    TicketAssignSerializer,
    TicketAttachmentSerializer,
    TicketCreateSerializer,
    TicketMessageCreateSerializer,
    TicketMessageSerializer,
    TicketPrioritySerializer,
    TicketSerializer,
    TicketStatusSerializer,
)


logger = logging.getLogger(__name__)


from apps.core.permissions import IsAdminUser  # noqa: E402


def generate_ticket_code():
    return f"TKT-{secrets.token_hex(5).upper()}"


# ============================================================
# AUDIT LOG HELPER
# ============================================================
def _log(request, action, target="", target_id=None, details=""):
    try:
        log_action(
            request=request,
            action=action,
            target=target,
            target_id=target_id,
            details=details,
        )
    except Exception:
        logger.exception("Failed to write audit log: %s", action)


class TicketViewSet(viewsets.GenericViewSet):
    """
        GET     /api/tickets/                      admin: all, user: own
        GET     /api/tickets/{id}/
        POST    /api/tickets/                      create (multipart OK)
        POST    /api/tickets/{id}/messages/        add message (+ files)
        POST    /api/tickets/{id}/attachments/     upload files to ticket
        POST    /api/tickets/{id}/status/          admin only
        POST    /api/tickets/{id}/priority/        admin only
        POST    /api/tickets/{id}/assign/          admin only
        DELETE  /api/tickets/{id}/                 admin or owner
    """

    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    # ── Rate limit tofauti: user 5/h, admin 100/h ──
    def get_throttles(self):
        if self.request.user.is_staff:
            self.throttle_scope = "support_ticket_admin"
        else:
            self.throttle_scope = "support_ticket"
        return super().get_throttles()

    def get_queryset(self):
        user = self.request.user
        qs = (
            Ticket.objects
            .select_related("user", "assigned_to")
            .prefetch_related("messages", "attachments")
        )
        if user.is_staff:
            return qs
        return qs.filter(user=user)

    def list(self, request):
        qs = self.get_queryset()
        status_filter = request.query_params.get("status")
        category_filter = request.query_params.get("category")
        _ALIASES = {"CLOSED": "COMPLETED"}
        if status_filter:
            sf = status_filter.upper()
            sf = _ALIASES.get(sf, sf)
            qs = qs.filter(status=sf)
        if category_filter:
            qs = qs.filter(category=category_filter.upper())
        page = self.paginate_queryset(qs)
        serializer = TicketSerializer(
            page if page is not None else qs,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(
            TicketSerializer(obj, context={"request": request}).data
        )

    @extend_schema(
        request=TicketCreateSerializer,
        responses={201: TicketSerializer},
    )
    def create(self, request):
        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        def _make_ticket(ticket_code):
            return Ticket.objects.create(
                code=ticket_code,
                subject=data["subject"],
                description=data.get("description", ""),
                category=data["category"],
                priority=data["priority"],
                user=request.user,
                user_name=request.user.name,
                user_email=request.user.email or "",
                # ── SLA: saa 24 kutoka sasa ──
                sla_deadline=timezone.now() + timedelta(hours=24),
            )

        try:
            ticket = _make_ticket(generate_ticket_code())
        except IntegrityError:
            ticket = _make_ticket(generate_ticket_code())

        if data.get("description"):
            msg = TicketMessage.objects.create(
                ticket=ticket,
                sender=TicketMessage.Sender.USER,
                sender_name=request.user.name,
                text=data["description"],
            )

            # ── Attachments za kwanza (kama zipo) ──
            files = request.FILES.getlist("attachments") or request.FILES.getlist("files")
            for f in files:
                TicketAttachment.objects.create(
                    ticket=ticket,
                    message=msg,
                    file=f,
                    name=f.name[:255],
                    uploaded_by=request.user,
                    uploaded_by_name=request.user.name,
                )

        _log(
            request,
            action="ticket.created",
            target="Ticket",
            target_id=ticket.id,
            details=f"Created ticket: {ticket.code} — {ticket.subject}",
        )

        return Response(
            TicketSerializer(ticket, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    # ============================================================
    # ADD MESSAGE (+ files, kama zipo)
    # ============================================================
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

        serializer = TicketMessageCreateSerializer(
            data=request.data,
            context={"files": request.FILES.getlist("attachments") or request.FILES.getlist("files")},
        )
        serializer.is_valid(raise_exception=True)

        text = serializer.validated_data["text"]
        files = request.FILES.getlist("attachments") or request.FILES.getlist("files")

        sender = (
            TicketMessage.Sender.ADMIN
            if request.user.is_staff
            else TicketMessage.Sender.USER
        )
        msg = TicketMessage.objects.create(
            ticket=ticket,
            sender=sender,
            sender_name=request.user.name,
            text=text or "[attachment]",
        )

        # ── Save attachments ──
        created_attachments = []
        for f in files:
            att = TicketAttachment.objects.create(
                ticket=ticket,
                message=msg,
                file=f,
                name=f.name[:255],
                uploaded_by=request.user,
                uploaded_by_name=request.user.name,
            )
            created_attachments.append(att)

        # ── Admin reply → clear SLA reminder flag ──
        if request.user.is_staff:
            ticket.save(update_fields=["updated_at"])
        else:
            ticket.save(update_fields=["updated_at"])

        _log(
            request,
            action="ticket.message_added",
            target="Ticket",
            target_id=ticket.id,
            details=(
                f"Message added to {ticket.code} "
                f"by {request.user.name} "
                f"(attachments: {len(created_attachments)})"
            ),
        )

        return Response(
            TicketMessageSerializer(
                msg, context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    # ============================================================
    # UPLOAD ATTACHMENTS PEKEE (bila message)
    # ============================================================
    @action(
        detail=True, methods=["post"], url_path="attachments",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_attachments(self, request, pk=None):
        ticket = get_object_or_404(self.get_queryset(), pk=pk)
        if ticket.status == Ticket.Status.CLOSED and not request.user.is_staff:
            return Response(
                {"detail": "Ticket imefungwa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        files = request.FILES.getlist("attachments") or request.FILES.getlist("files")
        if not files:
            return Response(
                {"detail": "Hakuna faili lililopokelewa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        for f in files:
            att = TicketAttachment.objects.create(
                ticket=ticket,
                file=f,
                name=f.name[:255],
                uploaded_by=request.user,
                uploaded_by_name=request.user.name,
            )
            created.append(att)

        _log(
            request,
            action="ticket.attachments_uploaded",
            target="Ticket",
            target_id=ticket.id,
            details=f"Uploaded {len(created)} attachments to {ticket.code}",
        )

        return Response(
            {
                "count": len(created),
                "attachments": TicketAttachmentSerializer(
                    created, many=True, context={"request": request},
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    # ============================================================
    # SET STATUS (admin only)
    # ============================================================
    @extend_schema(
        request=TicketStatusSerializer,
        responses={200: TicketSerializer},
    )
    @action(
        detail=True, methods=["post"], url_path="status",
        permission_classes=[IsAdminUser],
    )
    def set_status(self, request, pk=None):
        ticket = get_object_or_404(Ticket, pk=pk)
        serializer = TicketStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        old_status = ticket.status

        # ── GUARD: close lazima iwe resolved kwanza ──
        if new_status == Ticket.Status.CLOSED and old_status != Ticket.Status.RESOLVED:
            return Response(
                {
                    "detail": (
                        "Ticket inaweza kufungwa tu ikiwa imetatuliwa kwanza "
                        "(RESOLVED)."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ticket.status = new_status
        if new_status == Ticket.Status.RESOLVED and not ticket.resolved_at:
            ticket.resolved_at = timezone.now()
        ticket.save(update_fields=["status", "resolved_at", "updated_at"])

        _log(
            request,
            action="ticket.status_changed",
            target="Ticket",
            target_id=ticket.id,
            details=(
                f"Status changed for {ticket.code}: "
                f"{old_status} → {new_status}"
            ),
        )

        # ── Notify user ──
        try:
            from apps.notifications.services.notification import create_notification
            from apps.notifications.models import Notification

            create_notification(
                recipient=ticket.user,
                notification_type=Notification.NotificationType.GENERAL,
                title=f"Ticket {ticket.code} imeshughulikiwa",
                message=f"Hali mpya: {ticket.get_status_display()}",
                priority=Notification.Priority.HIGH,
                related_object_type="ticket",
                related_object_id=ticket.id,
                action_url=f"/dashboard/support/{ticket.id}",
            )
        except Exception:
            logger.exception("ticket notify failed")

        return Response(
            TicketSerializer(ticket, context={"request": request}).data
        )

    # ============================================================
    # SET PRIORITY (admin only)
    # ============================================================
    @extend_schema(
        request=TicketPrioritySerializer,
        responses={200: TicketSerializer},
    )
    @action(
        detail=True, methods=["post"], url_path="priority",
        permission_classes=[IsAdminUser],
    )
    def set_priority(self, request, pk=None):
        ticket = get_object_or_404(Ticket, pk=pk)
        serializer = TicketPrioritySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_priority = ticket.priority
        ticket.priority = serializer.validated_data["priority"]
        ticket.save(update_fields=["priority", "updated_at"])

        _log(
            request,
            action="ticket.priority_changed",
            target="Ticket",
            target_id=ticket.id,
            details=(
                f"Priority changed for {ticket.code}: "
                f"{old_priority} → {ticket.priority}"
            ),
        )

        return Response(
            TicketSerializer(ticket, context={"request": request}).data
        )

    # ============================================================
    # ASSIGN (admin only)
    # ============================================================
    @extend_schema(
        request=TicketAssignSerializer,
        responses={200: TicketSerializer},
    )
    @action(
        detail=True, methods=["post"], url_path="assign",
        permission_classes=[IsAdminUser],
    )
    def assign(self, request, pk=None):
        ticket = get_object_or_404(Ticket, pk=pk)
        serializer = TicketAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = get_object_or_404(
            User, pk=serializer.validated_data["staff_id"], is_staff=True,
        )
        old_staff = ticket.assigned_to_name or "—"
        ticket.assigned_to = staff
        ticket.assigned_to_name = staff.name
        ticket.save(update_fields=[
            "assigned_to", "assigned_to_name", "updated_at",
        ])

        _log(
            request,
            action="ticket.assigned",
            target="Ticket",
            target_id=ticket.id,
            details=(
                f"Assigned {ticket.code}: {old_staff} → {staff.name}"
            ),
        )

        return Response(
            TicketSerializer(ticket, context={"request": request}).data
        )

    # ============================================================
    # DESTROY
    # ============================================================
    def destroy(self, request, pk=None):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        if obj.user_id != request.user.id and not request.user.is_staff:
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )
        code = obj.code
        obj.delete(by=request.user, reason="Ticket deleted by owner/admin")

        _log(
            request,
            action="ticket.deleted",
            target="Ticket",
            target_id=obj.id,
            details=f"Deleted ticket: {code}",
        )

        return Response(
            {"detail": "Ticket imewekwa kwenye kikapu."},
            status=status.HTTP_200_OK,
        )