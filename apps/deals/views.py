# apps/deals/views.py
import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from apps.listings.models import Listing
from apps.tickets.models import Ticket, TicketMessage
from apps.tickets.serializers import DealReportSerializer

from .models import DealMessage, DealRoom, NegotiationOffer
from .permissions import IsDealParticipant, IsVerifiedDealUser
from .serializers_admin import AdminDealRoomSerializer
from .serializers import (
    DealMessageCreateSerializer,
    DealMessageSerializer,
    DealRoomAcceptOfferSerializer,
    DealRoomCancelSerializer,
    DealRoomCreateSerializer,
    DealRoomDetailSerializer,
    DealRoomListSerializer,
    DealRoomReopenSerializer,
    NegotiationOfferCreateSerializer,
    NegotiationOfferSerializer,
)
from .services.notifications import (
    notify_deal_room_cancelled,
    notify_deal_room_created,
    notify_new_offer,
    notify_offer_accepted,
    notify_offer_rejected,
)
from .services.ws_broadcast import (
    broadcast_deal_update,
    broadcast_new_message,
    broadcast_new_offer,
    broadcast_offer_update,
)


def _log(request, action, target="", target_id=None, details="", params=None):
    try:
        from apps.audit.services.audit import log_action
        log_action(
            request=request,
            action=action,
            target=target,
            target_id=target_id,
            details=details,
            params=params,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to write audit log: %s", action,
        )


def _mark_messages_read(deal_room, user):
    """
    Ujumbe wa mwenzake ambao haujasomwa unawekewa `read_at`. Inaitwa
    na endpoint ya `mark-read` PEKEE (frontend inaiita room inapokuwa
    wazi na inaonekana) — GET haiweki alama ya kusomwa.
    Admin (staff) hawaathiri hali hii. Inarudisha idadi iliyowekwa.
    """
    try:
        if user.is_staff:
            return 0
        if user.id not in (deal_room.buyer_id, deal_room.seller_id):
            return 0
        return (
            DealMessage.objects
            .filter(
                deal_room=deal_room,
                kind=DealMessage.Kind.USER,
                is_hidden=False,
                read_at__isnull=True,
            )
            .exclude(sender=user)
            .update(read_at=timezone.now())
        )
    except Exception:
        logger.exception(
            "Failed to mark deal messages read: %s", deal_room.pk,
        )
        return 0


def _generate_ticket_code():
    import secrets
    return f"TKT-{secrets.token_hex(5).upper()}"


logger = logging.getLogger(__name__)


def _deal_error(code, detail, http_status=status.HTTP_409_CONFLICT):
    """
    Kosa la kibiashara lenye `code` — frontend (apiErrors.js) inatumia `code`
    kuonyesha maelezo mahususi badala ya ujumbe ghafi.
    """
    return Response({"detail": detail, "code": code}, status=http_status)


def _notify_reopened(deal_room, reopened_by, note=""):
    """Mjulishe mwenzake. Haivunji reopen ikishindwa."""
    try:
        from .services.notifications import notify_deal_room_reopened
    except ImportError:
        return
    try:
        notify_deal_room_reopened(
            deal_room=deal_room, reopened_by=reopened_by, note=note,
        )
    except Exception:
        logger.exception(
            "Failed to notify deal room reopened: %s", deal_room.pk,
        )


@extend_schema_view(
    list=extend_schema(responses={200: DealRoomListSerializer(many=True)}),
    retrieve=extend_schema(responses={200: DealRoomDetailSerializer}),
    create=extend_schema(
        request=DealRoomCreateSerializer,
        responses={201: DealRoomDetailSerializer},
    ),
)
class DealRoomViewSet(viewsets.ModelViewSet):
    queryset = (
        DealRoom.objects
        .select_related(
            "listing", "listing__category", "buyer", "seller",
            "locked_by",
            "transaction", "transaction__reservation",
        )
        .prefetch_related("offers", "offers__offered_by")
    )

    http_method_names = ["get", "post", "head", "options"]

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["seller", "buyer", "status", "listing"]

    def get_serializer_class(self):
        if self.action == "create":
            return DealRoomCreateSerializer
        if self.action == "offer":
            return NegotiationOfferCreateSerializer
        if self.action in ("accept_offer", "decline_offer"):
            return DealRoomAcceptOfferSerializer
        if self.action == "cancel":
            return DealRoomCancelSerializer
        if self.action == "reopen":
            return DealRoomReopenSerializer
        if self.action == "report":
            return DealReportSerializer
        if self.action == "messages_create":
            return DealMessageCreateSerializer
        if self.action == "retrieve":
            if self.request.user.is_staff:
                return AdminDealRoomSerializer
            return DealRoomDetailSerializer
        if self.request.user.is_staff:
            return AdminDealRoomSerializer
        return DealRoomListSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsVerifiedDealUser()]
        if self.action in [
            "retrieve", "offer", "accept_offer", "decline_offer", "cancel",
            "messages_create", "messages_list", "mark_read",
            "report", "reopen",
        ]:
            return [
                permissions.IsAuthenticated(),
                IsVerifiedDealUser(),
                IsDealParticipant(),
            ]
        return [permissions.IsAuthenticated(), IsVerifiedDealUser()]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.is_staff:
            return qs

        role = self.request.query_params.get("role", "").strip().lower()

        if role == "buyer":
            return qs.filter(buyer=user)
        if role == "seller":
            return qs.filter(seller=user)

        return qs.filter(Q(buyer=user) | Q(seller=user))

    def update(self, request, *args, **kwargs):
        if "status" in request.data:
            return Response(
                {
                    "detail": (
                        "Hali ya Deal Room inabadilishwa kwa endpoints "
                        "maalum pekee (accept-offer / cancel)."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        existing = getattr(serializer, "_existing_deal_room", None)
        if existing:
            response_serializer = DealRoomDetailSerializer(
                existing,
                context={"request": request, "deal_room": existing},
            )
            return Response(
                response_serializer.data, status=status.HTTP_200_OK,
            )

        try:
            with transaction.atomic():
                deal_room = serializer.save()
                transaction.on_commit(
                    lambda: notify_deal_room_created(deal_room=deal_room)
                )
        except IntegrityError:
            existing = DealRoom.objects.filter(
                listing_id=serializer.validated_data["listing_id"],
                buyer=request.user,
            ).first()
            if existing:
                response_serializer = DealRoomDetailSerializer(
                    existing,
                    context={"request": request, "deal_room": existing},
                )
                return Response(
                    response_serializer.data, status=status.HTTP_200_OK,
                )
            raise

        try:
            from apps.leads.services.lead import upsert_lead_from_deal_room
            upsert_lead_from_deal_room(deal_room)
        except Exception:
            pass

        response_serializer = DealRoomDetailSerializer(
            deal_room,
            context={"request": request, "deal_room": deal_room},
        )
        return Response(
            response_serializer.data, status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        deal_room = self.get_object()
        serializer = self.get_serializer_class()(
            deal_room,
            context={"request": request, "deal_room": deal_room},
        )
        return Response(serializer.data)

    @extend_schema(
        responses={200: NegotiationOfferSerializer(many=True)},
    )
    @action(
        detail=True, methods=["get"],
        url_path="offers", url_name="offers-list",
    )
    def offers_list(self, request, pk=None):
        deal_room = self.get_object()
        qs = (
            NegotiationOffer.objects
            .filter(deal_room=deal_room)
            .select_related("offered_by")
            .order_by("created_at")
        )
        serializer = NegotiationOfferSerializer(
            qs, many=True,
            context={"request": request, "deal_room": deal_room},
        )
        return Response(serializer.data)

    @extend_schema(responses={200: None})
    @action(
        detail=True, methods=["get"],
        url_path="messages", url_name="messages-list",
    )
    def messages_list(self, request, pk=None):
        deal_room = self.get_object()
        qs = (
            DealMessage.objects
            .filter(deal_room=deal_room)
            .select_related("sender")
            .order_by("created_at")
        )
        if not request.user.is_staff:
            qs = qs.filter(is_hidden=False)
        return Response(
            DealMessageSerializer(
                qs, many=True, context={"request": request}
            ).data
        )

    @extend_schema(
        request=DealMessageCreateSerializer,
        responses={201: None},
    )
    @action(
        detail=True, methods=["post"],
        url_path="messages", url_name="messages-create",
    )
    def messages_create(self, request, pk=None):
        deal_room = self.get_object()

        if deal_room.admin_locked:
            return _deal_error(
                "DEAL_LOCKED",
                "Deal Room hii imesimamishwa na admin — huwezi kutuma "
                "ujumbe kwa sasa.",
            )

        serializer = DealMessageCreateSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)

        msg = DealMessage.objects.create(
            deal_room=deal_room,
            sender=request.user,
            text=serializer.validated_data.get("text", ""),
            attachment=serializer.validated_data.get("attachment"),
            kind=DealMessage.Kind.USER,
        )
        DealRoom.objects.filter(pk=deal_room.pk).update(
            updated_at=timezone.now()
        )

        # ✅ MPYA: broadcast ya ujumbe mpya
        attachment_url = None
        if msg.attachment:
            try:
                attachment_url = request.build_absolute_uri(
                    msg.attachment.url
                )
            except Exception:
                attachment_url = None

        transaction.on_commit(
            lambda: broadcast_new_message(
                room_id=deal_room.id,
                message_data={
                    "id": msg.id,
                    "text": msg.text or "",
                    "kind": msg.kind,
                    "sender_id": msg.sender_id,
                    "created_at": msg.created_at.isoformat(),
                    "attachment_url": attachment_url,
                    "offer_amount": None,
                },
            )
        )

        return Response(
            DealMessageSerializer(msg, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(request=None, responses={200: None})
    @action(
        detail=True, methods=["post"],
        url_path="mark-read", url_name="mark-read",
    )
    def mark_read(self, request, pk=None):
        deal_room = self.get_object()
        marked = _mark_messages_read(deal_room, request.user)
        return Response({"ok": True, "marked": marked})

    @extend_schema(responses={200: None})
    @action(
        detail=True, methods=["get"],
        url_path="payment-proof", url_name="payment-proof",
    )
    def payment_proof(self, request, pk=None):
        deal_room = self.get_object()
        txn = getattr(deal_room, "transaction", None)
        if not txn:
            return Response({"detail": "Transaction haipo."}, status=404)

        proof = getattr(txn, "final_payment_proof", None)
        if not proof:
            return Response(
                {"detail": "Ushahidi wa malipo haupo."}, status=404,
            )

        url = None
        try:
            url = request.build_absolute_uri(proof.url)
        except Exception:
            url = None

        return Response({
            "id": txn.id,
            "url": url,
            "reference": txn.final_payment_reference or "",
            "uploaded_at": txn.final_payment_uploaded_at,
            "confirmed": txn.seller_confirmed_payment,
            "confirmed_at": txn.seller_confirmed_at,
        })

    # ============================================================
    # REPORT
    # ============================================================
    @extend_schema(
        request=DealReportSerializer,
        responses={201: None},
    )
    @action(
        detail=True, methods=["post"],
        url_path="report", url_name="report",
    )
    @transaction.atomic
    def report(self, request, pk=None):
        deal_room = self.get_object()

        serializer = DealReportSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)

        reported_user_id = serializer.validated_data["reported_user_id"]
        reason = serializer.validated_data["reason"]
        details = serializer.validated_data["details"]

        if request.user.id == deal_room.buyer_id:
            reporter_role = "buyer"
            reported_user = deal_room.seller
        else:
            reporter_role = "seller"
            reported_user = deal_room.buyer

        subject = (
            f"Ripoti ya {reporter_role.upper()} dhidi ya "
            f"{reported_user.name} — Deal #{deal_room.id}"
        )
        description = (
            f"**Deal Room:** #{deal_room.id} — {deal_room.listing.title}\n"
            f"**Aliyeripoti:** {request.user.name} "
            f"(ID {request.user.id}, {reporter_role})\n"
            f"**Aliripotiwa:** {reported_user.name} "
            f"(ID {reported_user.id})\n"
            f"**Sababu:** {reason}\n\n"
            f"**Maelezo:**\n{details}"
        )

        ticket = Ticket.objects.create(
            code=_generate_ticket_code(),
            subject=subject[:255],
            description=description,
            category=Ticket.Category.DEAL_REPORT,
            priority=Ticket.Priority.HIGH,
            user=request.user,
            user_name=request.user.name,
            user_email=request.user.email or "",
            sla_deadline=timezone.now() + timedelta(hours=24),
            deal_room=deal_room,
            reported_user=reported_user,
            reported_user_name=reported_user.name,
            reporter_role=reporter_role,
            report_reason=reason,
        )

        TicketMessage.objects.create(
            ticket=ticket,
            sender=TicketMessage.Sender.USER,
            sender_name=request.user.name,
            text=description,
        )

        _log(
            request,
            action="deal.reported",
            target="Ticket",
            target_id=ticket.id,
            details={
                "sw": (
                    f"Mtumiaji {request.user.id} ({reporter_role}) amemripoti "
                    f"mtumiaji {reported_user.id} kwenye deal #{deal_room.id} — "
                    f"sababu={reason}"
                ),
                "en": (
                    f"User {request.user.id} ({reporter_role}) reported "
                    f"user {reported_user.id} in deal #{deal_room.id} — "
                    f"reason={reason}"
                ),
            },
        )

        try:
            from apps.notifications.services.notification import (
                create_notification_for_admins,
            )
            from apps.notifications.models import Notification

            create_notification_for_admins(
                notification_type=Notification.NotificationType.GENERAL,
                title=f"Ripoti Mpya ya Deal: {ticket.code}",
                message=(
                    f"{request.user.name} ({reporter_role}) amemripoti "
                    f"{reported_user.name} — sababu: {reason}"
                ),
                priority=Notification.Priority.URGENT,
                related_object_type="ticket",
                related_object_id=ticket.id,
                action_url=f"/smk-control-9x7k/support?ticket={ticket.id}",
            )
        except Exception:
            logger.exception(
                "Failed to notify admins of deal report %s", ticket.id,
            )

        return Response(
            {
                "ok": True,
                "ticket_id": ticket.id,
                "ticket_code": ticket.code,
                "message": (
                    "Ripoti yako imetumwa. Timu yetu itachukua hatua "
                    "ndani ya saa 24."
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    # ============================================================
    # OFFER
    # ============================================================
    @extend_schema(
        request=NegotiationOfferCreateSerializer,
        responses={201: NegotiationOfferSerializer},
    )
    @action(detail=True, methods=["post"], url_path="offers", url_name="offers")
    @transaction.atomic
    def offer(self, request, pk=None):
        deal_room = self.get_object()

        if deal_room.admin_locked:
            return _deal_error(
                "DEAL_LOCKED",
                "Deal Room hii imesimamishwa na admin — haiwezi kupokea "
                "offers mpya kwa sasa.",
            )

        if deal_room.status not in [
            DealRoom.Status.OPEN, DealRoom.Status.NEGOTIATING,
        ]:
            return Response(
                {
                    "detail": (
                        "Deal Room hii haipokei offers mpya. "
                        f"Hali ya sasa ni {deal_room.status}."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = NegotiationOfferCreateSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)

        responded_to_id = serializer.validated_data.get("responded_to")
        responded_to = None

        if responded_to_id:
            responded_to = (
                NegotiationOffer.objects
                .select_for_update()
                .filter(pk=responded_to_id, deal_room=deal_room)
                .first()
            )

            if not responded_to:
                raise ValidationError({
                    "responded_to": "Offer uliyochagua haijapatikana."
                })

            if responded_to.offered_by_id == request.user.id:
                raise ValidationError({
                    "responded_to": "Huwezi kujibu offer yako mwenyewe."
                })

            if responded_to.status != NegotiationOffer.Status.PENDING:
                raise ValidationError({
                    "responded_to": "Offer hii haipo kwenye hali ya PENDING."
                })

            responded_to.status = NegotiationOffer.Status.COUNTERED
            responded_to.save(update_fields=["status", "updated_at"])

        new_offer = NegotiationOffer.objects.create(
            deal_room=deal_room,
            offered_by=request.user,
            amount=serializer.validated_data["amount"],
            message=serializer.validated_data.get("message", ""),
            status=NegotiationOffer.Status.PENDING,
            responded_to=responded_to,
        )

        if deal_room.status == DealRoom.Status.OPEN:
            deal_room.status = DealRoom.Status.NEGOTIATING
            deal_room.save(update_fields=["status", "updated_at"])
        else:
            deal_room.save(update_fields=["updated_at"])

        # ✅ MPYA: broadcast ya ofa mpya
        transaction.on_commit(
            lambda: broadcast_new_offer(
                room_id=deal_room.id,
                offer_data={
                    "id": new_offer.id,
                    "offer_amount": str(new_offer.amount),
                    "sender_id": new_offer.offered_by_id,
                    "created_at": new_offer.created_at.isoformat(),
                },
            )
        )
        transaction.on_commit(
            lambda: broadcast_deal_update(
                room_id=deal_room.id,
                deal_data={"current_offer": str(new_offer.amount)},
            )
        )

        transaction.on_commit(
            lambda: notify_new_offer(deal_room=deal_room, offer=new_offer)
        )

        try:
            from apps.leads.services.lead import upsert_lead_from_deal_room
            upsert_lead_from_deal_room(deal_room)
        except Exception:
            pass

        return Response(
            NegotiationOfferSerializer(
                new_offer,
                context={"request": request, "deal_room": deal_room},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=DealRoomAcceptOfferSerializer,
        responses={200: DealRoomDetailSerializer},
    )
    @action(
        detail=True, methods=["post"],
        url_path="accept-offer", url_name="accept-offer",
    )
    @transaction.atomic
    def accept_offer(self, request, pk=None):
        deal_room = get_object_or_404(
            DealRoom.objects
            .select_for_update(of=("self",))
            .select_related("listing", "listing__category", "buyer", "seller"),
            pk=pk,
        )
        self.check_object_permissions(request, deal_room)

        if deal_room.admin_locked:
            return _deal_error(
                "DEAL_LOCKED",
                "Deal Room hii imesimamishwa na admin — haiwezi kukubali "
                "offer kwa sasa.",
            )

        if deal_room.status not in [
            DealRoom.Status.OPEN, DealRoom.Status.NEGOTIATING,
        ]:
            return Response(
                {
                    "detail": (
                        "Deal Room hii haiwezi kukubali offer. "
                        f"Hali ya sasa ni {deal_room.status}."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DealRoomAcceptOfferSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)

        offer_id = serializer.validated_data["offer_id"]
        offer = (
            NegotiationOffer.objects
            .select_for_update(of=("self",))
            .select_related("offered_by")
            .filter(pk=offer_id, deal_room=deal_room)
            .first()
        )

        if not offer:
            raise ValidationError({
                "offer_id": "Offer haijapatikana kwenye Deal Room hii."
            })

        if offer.offered_by_id == request.user.id:
            raise ValidationError({
                "offer_id": "Huwezi kukubali offer yako mwenyewe."
            })

        if offer.status != NegotiationOffer.Status.PENDING:
            raise ValidationError({
                "offer_id": (
                    "Offer hii haiwezi kukubaliwa kwa sababu hali yake "
                    "si PENDING."
                ),
            })

        offer.status = NegotiationOffer.Status.ACCEPTED
        offer.save(update_fields=["status", "updated_at"])

        siblings_pending = NegotiationOffer.objects.filter(
            deal_room=deal_room,
            status=NegotiationOffer.Status.PENDING,
        ).exclude(pk=offer.pk)

        sibling_list = list(siblings_pending)
        siblings_pending.update(
            status=NegotiationOffer.Status.REJECTED,
            updated_at=timezone.now(),
        )

        deal_room.status = DealRoom.Status.ACCEPTED
        deal_room.agreed_price = offer.amount
        deal_room.agreed_at = timezone.now()
        deal_room.save(update_fields=[
            "status", "agreed_price", "agreed_at", "updated_at",
        ])

        listing = deal_room.listing
        if listing.status == Listing.Status.LIVE:
            listing.status = Listing.Status.RESERVED
            listing.save(update_fields=["status", "updated_at"])

        sibling_rooms = (
            DealRoom.objects
            .select_for_update()
            .filter(
                listing=deal_room.listing,
                status__in=[
                    DealRoom.Status.OPEN,
                    DealRoom.Status.NEGOTIATING,
                ],
            )
            .exclude(pk=deal_room.pk)
            .order_by("pk")
        )

        sibling_room_list = list(sibling_rooms)
        sibling_rooms.update(
            status=DealRoom.Status.CANCELLED,
            updated_at=timezone.now(),
        )

        for sib in sibling_room_list:
            sib.offers.filter(
                status=NegotiationOffer.Status.PENDING,
            ).update(
                status=NegotiationOffer.Status.CANCELLED,
                updated_at=timezone.now(),
            )
            transaction.on_commit(
                lambda sib=sib: notify_deal_room_cancelled(
                    deal_room=sib,
                    cancelled_by=request.user,
                    reason="Tangazo limeshachukuliwa na mnunuzi mwingine.",
                )
            )

        transaction.on_commit(
            lambda: notify_offer_accepted(deal_room=deal_room, offer=offer)
        )

        for rejected in sibling_list:
            transaction.on_commit(
                lambda rejected=rejected: notify_offer_rejected(
                    deal_room=deal_room, offer=rejected
                )
            )

        # ✅ MPYA: broadcast ya offer update + deal update
        transaction.on_commit(
            lambda: broadcast_offer_update(
                room_id=deal_room.id,
                offer_data={
                    "id": offer.id,
                    "status": offer.status,
                },
            )
        )
        transaction.on_commit(
            lambda: broadcast_deal_update(
                room_id=deal_room.id,
                deal_data={
                    "status": deal_room.status,
                    "agreed_price": (
                        str(deal_room.agreed_price)
                        if deal_room.agreed_price
                        else None
                    ),
                    "agreed_at": (
                        deal_room.agreed_at.isoformat()
                        if deal_room.agreed_at
                        else None
                    ),
                },
            )
        )

        return Response(
            DealRoomDetailSerializer(
                deal_room,
                context={"request": request, "deal_room": deal_room},
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=DealRoomAcceptOfferSerializer,
        responses={200: NegotiationOfferSerializer},
    )
    @action(
        detail=True, methods=["post"],
        url_path="decline-offer", url_name="decline-offer",
    )
    @transaction.atomic
    def decline_offer(self, request, pk=None):
        deal_room = get_object_or_404(
            DealRoom.objects.select_for_update(of=("self",)),
            pk=pk,
        )
        self.check_object_permissions(request, deal_room)

        serializer = DealRoomAcceptOfferSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)

        offer = (
            NegotiationOffer.objects
            .select_for_update(of=("self",))
            .select_related("offered_by")
            .get(pk=serializer.validated_data["offer_id"], deal_room=deal_room)
        )
        offer.status = NegotiationOffer.Status.REJECTED
        offer.save(update_fields=["status", "updated_at"])
        deal_room.save(update_fields=["updated_at"])

        # ✅ MPYA: broadcast ya offer update
        transaction.on_commit(
            lambda: broadcast_offer_update(
                room_id=deal_room.id,
                offer_data={
                    "id": offer.id,
                    "status": offer.status,
                },
            )
        )

        transaction.on_commit(
            lambda: notify_offer_rejected(deal_room=deal_room, offer=offer)
        )

        return Response(
            NegotiationOfferSerializer(
                offer,
                context={"request": request, "deal_room": deal_room},
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=DealRoomCancelSerializer,
        responses={200: DealRoomDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="cancel", url_name="cancel")
    @transaction.atomic
    def cancel(self, request, pk=None):
        deal_room = get_object_or_404(
            DealRoom.objects
            .select_for_update(of=("self",))
            .select_related("listing", "listing__category", "buyer", "seller"),
            pk=pk,
        )
        self.check_object_permissions(request, deal_room)

        if deal_room.admin_locked and not request.user.is_staff:
            return _deal_error(
                "DEAL_LOCKED",
                "Deal Room hii imesimamishwa na admin — huwezi kuifunga "
                "kwa sasa.",
            )

        if deal_room.status not in [
            DealRoom.Status.OPEN, DealRoom.Status.NEGOTIATING,
        ]:
            return Response(
                {
                    "detail": (
                        "Deal Room hii haiwezi kufungwa. "
                        f"Hali ya sasa ni {deal_room.status}."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DealRoomCancelSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)

        cancellation_reason = serializer.validated_data.get("reason", "")

        deal_room.status = DealRoom.Status.CANCELLED

        if request.user.is_staff:
            deal_room.cancelled_by_admin = True
            deal_room.save(update_fields=[
                "status", "cancelled_by_admin", "updated_at",
            ])
        else:
            deal_room.save(update_fields=["status", "updated_at"])

        NegotiationOffer.objects.filter(
            deal_room=deal_room,
            status=NegotiationOffer.Status.PENDING,
        ).update(
            status=NegotiationOffer.Status.CANCELLED,
            updated_at=timezone.now(),
        )

        if request.user.is_staff:
            _log(
                request,
                action="deal.cancelled_by_admin",
                target="DealRoom",
                target_id=deal_room.id,
                details={
                    "sw": (
                        f"Admin amefuta Deal Room #{deal_room.id} "
                        f"(tangazo: {deal_room.listing.title}). "
                        f"Sababu: {cancellation_reason or '—'}"
                    ),
                    "en": (
                        f"Admin cancelled Deal Room #{deal_room.id} "
                        f"(listing: {deal_room.listing.title}). "
                        f"Reason: {cancellation_reason or '—'}"
                    ),
                },
            )

        transaction.on_commit(
            lambda: notify_deal_room_cancelled(
                deal_room=deal_room,
                cancelled_by=request.user,
                reason=cancellation_reason,
            )
        )

        # ✅ MPYA: broadcast ya deal update
        transaction.on_commit(
            lambda: broadcast_deal_update(
                room_id=deal_room.id,
                deal_data={
                    "status": deal_room.status,
                    "cancelled_by_admin": deal_room.cancelled_by_admin,
                },
            )
        )

        return Response(
            DealRoomDetailSerializer(
                deal_room,
                context={"request": request, "deal_room": deal_room},
            ).data,
            status=status.HTTP_200_OK,
        )

    # ============================================================
    # REOPEN
    # ============================================================
    @extend_schema(
        request=DealRoomReopenSerializer,
        responses={200: DealRoomDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="reopen", url_name="reopen")
    @transaction.atomic
    def reopen(self, request, pk=None):
        deal_room = get_object_or_404(
            DealRoom.objects
            .select_for_update(of=("self",))
            .select_related("listing", "listing__category", "buyer", "seller"),
            pk=pk,
        )
        self.check_object_permissions(request, deal_room)

        if deal_room.cancelled_by_admin:
            return _deal_error(
                "CANCELLED_BY_ADMIN",
                "Deal hii ilighairiwa na msimamizi — haiwezi kufufuliwa "
                "na mimi/mwenzako. Wasiliana na support@sokomkononi.co.tz.",
                status.HTTP_403_FORBIDDEN,
            )

        if deal_room.admin_locked:
            return _deal_error(
                "DEAL_LOCKED",
                "Deal Room hii imesimamishwa na admin — haiwezi kufufuliwa "
                "kwa sasa.",
            )

        if request.user.id not in (deal_room.buyer_id, deal_room.seller_id):
            return _deal_error(
                "NOT_DEAL_PARTICIPANT",
                "Ni mnunuzi au muuzaji wa deal hii pekee anayeweza kuifufua.",
                status.HTTP_403_FORBIDDEN,
            )

        serializer = DealRoomReopenSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)
        note = serializer.validated_data.get("note", "")

        detail_context = {"request": request, "deal_room": deal_room}

        if deal_room.status in (
            DealRoom.Status.OPEN, DealRoom.Status.NEGOTIATING,
        ):
            return Response(
                DealRoomDetailSerializer(deal_room, context=detail_context).data,
                status=status.HTTP_200_OK,
            )

        if deal_room.status != DealRoom.Status.CANCELLED:
            return _deal_error(
                "DEAL_NOT_REOPENABLE",
                "Deal Room hii haiwezi kufufuliwa. "
                f"Hali ya sasa ni {deal_room.status}.",
            )

        if getattr(deal_room, "transaction", None) is not None:
            return _deal_error(
                "DEAL_HAS_TRANSACTION",
                "Deal hii ilishafika hatua ya reservation au malipo, kwa hiyo "
                "inahitaji kukaguliwa na support kabla ya kufufuliwa.",
            )

        max_reopens = getattr(settings, "DEAL_REOPEN_MAX", 3)
        if deal_room.reopened_count >= max_reopens:
            return _deal_error(
                "REOPEN_LIMIT_REACHED",
                "Mazungumzo haya yamefufuliwa mara nyingi mno "
                f"({deal_room.reopened_count}/{max_reopens}).",
            )

        if deal_room.listing.status != Listing.Status.LIVE:
            return _deal_error(
                "LISTING_UNAVAILABLE",
                "Tangazo hili halipatikani tena (limeuzwa, limewekwa na mtu "
                "mwingine, au limeondolewa).",
            )

        active_elsewhere = (
            DealRoom.objects
            .filter(
                listing_id=deal_room.listing_id,
                buyer_id=deal_room.buyer_id,
                status__in=[
                    DealRoom.Status.OPEN,
                    DealRoom.Status.NEGOTIATING,
                    DealRoom.Status.ACCEPTED,
                ],
            )
            .exclude(pk=deal_room.pk)
            .exists()
        )
        if active_elsewhere:
            return _deal_error(
                "ACTIVE_DEAL_EXISTS",
                "Kuna Deal Room nyingine iliyo wazi kwa tangazo hili.",
            )

        deal_room.status = DealRoom.Status.NEGOTIATING
        deal_room.agreed_price = None
        deal_room.agreed_at = None
        deal_room.reopened_at = timezone.now()
        deal_room.reopened_count += 1
        try:
            with transaction.atomic():
                deal_room.save(update_fields=[
                    "status", "agreed_price", "agreed_at",
                    "reopened_at", "reopened_count", "updated_at",
                ])
        except IntegrityError:
            return _deal_error(
                "ACTIVE_DEAL_EXISTS",
                "Kuna Deal Room nyingine iliyo wazi kwa tangazo hili.",
            )

        who = getattr(request.user, "name", "") or ""
        DealMessage.objects.create(
            deal_room=deal_room,
            sender=request.user,
            text=(
                f"Mazungumzo yamefufuliwa{f' na {who}' if who else ''}. / "
                f"Conversation reopened{f' by {who}' if who else ''}."
            ),
            kind=DealMessage.Kind.USER,
        )
        if note:
            DealMessage.objects.create(
                deal_room=deal_room, sender=request.user, text=note,
                kind=DealMessage.Kind.USER,
            )

        _log(
            request,
            action="deal.reopened",
            target="DealRoom",
            target_id=deal_room.id,
            details={
                "sw": (
                    f"Mtumiaji {request.user.id} amefufua Deal Room "
                    f"#{deal_room.id} (tangazo: {deal_room.listing.title}), "
                    f"mara ya {deal_room.reopened_count}."
                ),
                "en": (
                    f"User {request.user.id} reopened Deal Room "
                    f"#{deal_room.id} (listing: {deal_room.listing.title}), "
                    f"reopen #{deal_room.reopened_count}."
                ),
            },
        )

        transaction.on_commit(
            lambda: _notify_reopened(deal_room, request.user, note)
        )

        # ✅ MPYA: broadcast ya deal update
        transaction.on_commit(
            lambda: broadcast_deal_update(
                room_id=deal_room.id,
                deal_data={
                    "status": deal_room.status,
                    "reopened_at": (
                        deal_room.reopened_at.isoformat()
                        if deal_room.reopened_at
                        else None
                    ),
                    "reopened_count": deal_room.reopened_count,
                },
            )
        )

        try:
            from apps.leads.services.lead import upsert_lead_from_deal_room
            upsert_lead_from_deal_room(deal_room)
        except Exception:
            pass

        return Response(
            DealRoomDetailSerializer(deal_room, context=detail_context).data,
            status=status.HTTP_200_OK,
        )