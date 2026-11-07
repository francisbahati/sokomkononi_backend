import logging
import secrets

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _, override

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
from ._lang import user_lang


logger = logging.getLogger(__name__)


from apps.core.permissions import IsAdminUser  # noqa: E402


def generate_ticket_code():
    return f"TKT-{secrets.token_hex(5).upper()}"


# ============================================================
# AUDIT LOG HELPER
# ============================================================
def _log(request, action, target="", target_id=None, details="", params=None):
    try:
        log_action(
            request=request,
            action=action,
            target=target,
            target_id=target_id,
            details=details,
            params=params,
        )
    except Exception:
        logger.exception("Failed to write audit log: %s", action)


# ============================================================
# NOTIFICATION HELPERS
# ============================================================
def _notify_admins_of_new_ticket(ticket):
    """
    Mjulishe admins wote ticket mpya imetumwa.
    """
    try:
        from apps.notifications.services.notification import (
            create_notification_for_admins,
        )
        from apps.notifications.models import Notification

        create_notification_for_admins(
            notification_type=Notification.NotificationType.GENERAL,
            title=f"Ticket Mpya: {ticket.code}",
            message=(
                f"Kutoka kwa {ticket.user_name or ticket.user_email}: "
                f"{ticket.subject}"
            ),
            priority=Notification.Priority.HIGH,
            related_object_type="ticket",
            related_object_id=ticket.id,
            action_url=f"/smk-control-9x7k/support?ticket={ticket.id}",
        )
    except Exception:
        logger.exception(
            "Failed to notify admins about ticket %s", ticket.id,
        )


def _notify_user_of_reply(ticket, reply_text):
    """
    Mjulishe mtumiaji kuwa admin amejibu ticket yake.
    """
    try:
        from apps.notifications.services.notification import create_notification
        from apps.notifications.models import Notification

        lang = user_lang(ticket.user)
        # Preview ndogo ya ujumbe
        preview = (reply_text or "").strip()
        if len(preview) > 120:
            preview = preview[:117] + "..."

        with override(lang):
            create_notification(
                recipient=ticket.user,
                notification_type=Notification.NotificationType.GENERAL,
                title=_("Jibu jipya kwenye Ticket {code}").format(
                    code=ticket.code,
                ),
                message=preview or _("Admin amejibu ticket yako."),
                priority=Notification.Priority.HIGH,
                related_object_type="ticket",
                related_object_id=ticket.id,
                action_url=f"/dashboard/safety?ticket={ticket.id}",
                side="both",
            )
    except Exception:
        logger.exception(
            "Failed to notify user of ticket reply %s", ticket.id,
        )


class TicketViewSet(viewsets.GenericViewSet):
    """
    GET     /api/tickets/
    GET     /api/tickets/{id}/
    POST    /api/tickets/
    POST    /api/tickets/{id}/messages/
    POST    /api/tickets/{id}/attachments/
    POST    /api/tickets/{id}/status/
    POST    /api/tickets/{id}/priority/
    POST    /api/tickets/{id}/assign/
    DELETE  /api/tickets/{id}/
    """

    serializer_class = TicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

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
            .select_related("user", "user__preferences", "assigned_to")
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

        # ✅ Deal Report fields (optional)
        deal_room_id = data.get("deal_room")
        reported_user_id = data.get("reported_user")
        reported_user_name = data.get("reported_user_name", "")
        reporter_role = data.get("reporter_role", "")
        report_reason = data.get("report_reason", "")

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
                sla_deadline=timezone.now() + timedelta(hours=24),
                # ✅ Deal Report context (null kama haipo)
                deal_room_id=deal_room_id or None,
                reported_user_id=reported_user_id or None,
                reported_user_name=reported_user_name or "",
                reporter_role=reporter_role or "",
                report_reason=report_reason or "",
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

            files = (
                request.FILES.getlist("attachments")
                or request.FILES.getlist("files")
            )
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
            params={"code": ticket.code, "name": ticket.subject},
        )

        # ✅ Arifa kwa admin
        _notify_admins_of_new_ticket(ticket)

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
            context={
                "files": (
                    request.FILES.getlist("attachments")
                    or request.FILES.getlist("files")
                )
            },
        )
        serializer.is_valid(raise_exception=True)

        text = serializer.validated_data["text"]
        files = (
            request.FILES.getlist("attachments")
            or request.FILES.getlist("files")
        )

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

        ticket.save(update_fields=["updated_at"])

        _log(
            request,
            action="ticket.message_added",
            target="Ticket",
            target_id=ticket.id,
            params={
                "code": ticket.code,
                "user": request.user.name,
                "count": len(created_attachments),
            },
        )

        # ✅ Arifa kwa mtumiaji kama admin amejibu
        if request.user.is_staff:
            _notify_user_of_reply(ticket, text)

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

        files = (
            request.FILES.getlist("attachments")
            or request.FILES.getlist("files")
        )
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
            params={"count": len(created), "code": ticket.code},
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
            params={
                "code": ticket.code,
                "old": old_status,
                "new": new_status,
            },
        )

        try:
            from apps.notifications.services.notification import create_notification
            from apps.notifications.models import Notification

            lang = user_lang(ticket.user)
            with override(lang):
                create_notification(
                    recipient=ticket.user,
                    notification_type=Notification.NotificationType.GENERAL,
                    title=_("Ticket {code} imeshughulikiwa").format(
                        code=ticket.code,
                    ),
                    message=_("Hali mpya: {status}").format(
                        status=ticket.get_status_display(),
                    ),
                    priority=Notification.Priority.HIGH,
                    related_object_type="ticket",
                    related_object_id=ticket.id,
                    action_url=f"/dashboard/safety?ticket={ticket.id}",
                    side="both",
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
            params={
                "code": ticket.code,
                "old": old_priority,
                "new": ticket.priority,
            },
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
            params={
                "code": ticket.code,
                "old": old_staff,
                "new": staff.name,
            },
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
            params={"code": code},
        )

        return Response(
            {"detail": "Ticket imewekwa kwenye kikapu."},
            status=status.HTTP_200_OK,
        )