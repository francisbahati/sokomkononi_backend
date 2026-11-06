# apps/deals/views_admin.py
"""
Admin — Deal Rooms management.

Actions:
- GET  /api/admin/deals/                     → list (paginated)
- GET  /api/admin/deals/{id}/                → detail
- POST /api/admin/deals/{id}/admin-message/  → tuma ujumbe kama admin
- POST /api/admin/deals/{id}/lock/           → simamisha room
- POST /api/admin/deals/{id}/unlock/         → fungua room
- POST /api/admin/deals/{id}/cancel/         → ghairi deal (haiwezi kufufuliwa)
"""
import logging

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DealMessage, DealRoom, NegotiationOffer
from .serializers_admin import (
    AdminDealCancelSerializer,
    AdminDealLockSerializer,
    AdminDealMessageCreateSerializer,
    AdminDealMessageSerializer,
    AdminDealRoomSerializer,
    AdminDealUnlockSerializer,
)

logger = logging.getLogger(__name__)


def _log(request, action, target="", target_id=None, details="", params=None):
    """Audit logging — haivunji action ikishindwa."""
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
        logger.exception("Failed to write audit log: %s", action)


def _notify_safe(fn, **kwargs):
    """Arifa haivunji action ikishindwa."""
    try:
        fn(**kwargs)
    except Exception:
        logger.exception("Notification failed: %s", fn.__name__)


class AdminDealRoomViewSet(viewsets.GenericViewSet):
    """
    Admin anaweza kuona deals zote na kuchukua hatua za moderation:
    kutuma ujumbe, kusimamisha, kufungua, na kughairi.
    """
    serializer_class = AdminDealRoomSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = (
        DealRoom.objects
        .select_related(
            "listing", "listing__category", "buyer", "seller",
            "locked_by",
            "transaction", "transaction__reservation",
        )
        .prefetch_related(
            "offers", "offers__offered_by",
            "messages", "messages__sender",
        )
        .order_by("-updated_at")
    )

    # ============================================================
    # LIST / RETRIEVE
    # ============================================================
    def list(self, request):
        qs = self.get_queryset()

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())

        locked_filter = request.query_params.get("admin_locked")
        if locked_filter in ("true", "1", "True"):
            qs = qs.filter(admin_locked=True)
        elif locked_filter in ("false", "0", "False"):
            qs = qs.filter(admin_locked=False)

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

    # ============================================================
    # 1. ADMIN-MESSAGE — admin anatuma ujumbe kwenye room
    # ============================================================
    @action(
        detail=True, methods=["post"],
        url_path="admin-message", url_name="admin-message",
    )
    def admin_message(self, request, pk=None):
        """
        Admin anatuma ujumbe wa aina `kind=ADMIN`. Ujumbe unaonekana
        kwa pande zote mbili kwenye room. Arifa inatumwa kwa wote.
        """
        deal_room = self.get_object()

        serializer = AdminDealMessageCreateSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)

        text = serializer.validated_data["text"]

        with transaction.atomic():
            msg = DealMessage.objects.create(
                deal_room=deal_room,
                sender=request.user,
                text=text,
                kind=DealMessage.Kind.ADMIN,
            )
            DealRoom.objects.filter(pk=deal_room.pk).update(
                updated_at=timezone.now()
            )

            _log(
                request,
                action="deal.admin_message_sent",
                target="DealRoom",
                target_id=deal_room.id,
                details={
                    "sw": (
                        f"Admin ametuma ujumbe kwenye Deal Room "
                        f"#{deal_room.id}: {text[:120]}"
                    ),
                    "en": (
                        f"Admin sent message to Deal Room "
                        f"#{deal_room.id}: {text[:120]}"
                    ),
                },
            )

        # Arifa kwa pande zote mbili
        def _notify():
            from .services.notifications import notify_admin_message
            notify_admin_message(deal_room=deal_room, text=text)

        transaction.on_commit(lambda: _notify_safe(_notify))

        # Frontend (`adminSendMessageAsync`) inasoma: id, sender_id,
        # sender_name, text, created_at kutoka kwenye response hii.
        return Response(
            AdminDealMessageSerializer(msg).data,
            status=status.HTTP_201_CREATED,
        )

    # ============================================================
    # 3. LOCK — simamisha room
    # ============================================================
    @action(
        detail=True, methods=["post"],
        url_path="lock", url_name="lock",
    )
    def lock(self, request, pk=None):
        """
        Admin anasimamisha room. Ujumbe, offers, na kukubali offers
        zote zinasimama. Room haifutwi — inaweza kufunguliwa.
        """
        deal_room = self.get_object()

        serializer = AdminDealLockSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        with transaction.atomic():
            deal_room = (
                DealRoom.objects
                .select_for_update(of=("self",))
                .get(pk=deal_room.pk)
            )
            deal_room.admin_locked = True
            deal_room.locked_reason = reason
            deal_room.locked_at = timezone.now()
            deal_room.locked_by = request.user
            deal_room.save(update_fields=[
                "admin_locked", "locked_reason", "locked_at",
                "locked_by", "updated_at",
            ])

            _log(
                request,
                action="deal.locked_by_admin",
                target="DealRoom",
                target_id=deal_room.id,
                details={
                    "sw": (
                        f"Admin amesimamisha Deal Room #{deal_room.id}. "
                        f"Sababu: {reason}"
                    ),
                    "en": (
                        f"Admin locked Deal Room #{deal_room.id}. "
                        f"Reason: {reason}"
                    ),
                },
            )

        def _notify():
            from .services.notifications import notify_deal_room_locked
            notify_deal_room_locked(
                deal_room=deal_room,
                reason=reason,
                locked_by=request.user,
            )

        transaction.on_commit(lambda: _notify_safe(_notify))

        return Response(
            AdminDealRoomSerializer(
                deal_room, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    # ============================================================
    # UNLOCK — fungua room
    # ============================================================
    @action(
        detail=True, methods=["post"],
        url_path="unlock", url_name="unlock",
    )
    def unlock(self, request, pk=None):
        """Admin anafungua room iliyosimamishwa."""
        deal_room = self.get_object()

        serializer = AdminDealUnlockSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")

        with transaction.atomic():
            deal_room = (
                DealRoom.objects
                .select_for_update(of=("self",))
                .get(pk=deal_room.pk)
            )
            deal_room.admin_locked = False
            deal_room.locked_reason = ""
            deal_room.locked_at = None
            deal_room.locked_by = None
            deal_room.save(update_fields=[
                "admin_locked", "locked_reason", "locked_at",
                "locked_by", "updated_at",
            ])

            _log(
                request,
                action="deal.unlocked_by_admin",
                target="DealRoom",
                target_id=deal_room.id,
                details={
                    "sw": (
                        f"Admin amefungua Deal Room #{deal_room.id}."
                        + (f" Maelezo: {reason}" if reason else "")
                    ),
                    "en": (
                        f"Admin unlocked Deal Room #{deal_room.id}."
                        + (f" Note: {reason}" if reason else "")
                    ),
                },
            )

        def _notify():
            from .services.notifications import notify_deal_room_unlocked
            notify_deal_room_unlocked(
                deal_room=deal_room, unlocked_by=request.user,
            )

        transaction.on_commit(lambda: _notify_safe(_notify))

        return Response(
            AdminDealRoomSerializer(
                deal_room, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    # ============================================================
    # 5. CANCEL — admin anaghairi (haiwezi kufufuliwa)
    # ============================================================
    @action(
        detail=True, methods=["post"],
        url_path="cancel", url_name="cancel",
    )
    def cancel(self, request, pk=None):
        """
        Admin anaghairi Deal Room. Sababu ni lazima.
        `cancelled_by_admin=True` inazuia watumiaji kufufua.
        """
        deal_room = self.get_object()

        serializer = AdminDealCancelSerializer(
            data=request.data,
            context={"request": request, "deal_room": deal_room},
        )
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]

        with transaction.atomic():
            deal_room = (
                DealRoom.objects
                .select_for_update(of=("self",))
                .get(pk=deal_room.pk)
            )

            deal_room.status = DealRoom.Status.CANCELLED
            deal_room.cancelled_by_admin = True
            deal_room.save(update_fields=[
                "status", "cancelled_by_admin", "updated_at",
            ])

            NegotiationOffer.objects.filter(
                deal_room=deal_room,
                status=NegotiationOffer.Status.PENDING,
            ).update(
                status=NegotiationOffer.Status.CANCELLED,
                updated_at=timezone.now(),
            )

            # Ujumbe wa mfumo ndani ya room — kama `kind=ADMIN` ili uonekane
            DealMessage.objects.create(
                deal_room=deal_room,
                sender=request.user,
                text=(
                    f"Deal Room imeghairiwa na msimamizi. Sababu: {reason}"
                    f" / Deal Room was cancelled by admin. Reason: {reason}"
                ),
                kind=DealMessage.Kind.ADMIN,
            )

            _log(
                request,
                action="deal.cancelled_by_admin",
                target="DealRoom",
                target_id=deal_room.id,
                details={
                    "sw": (
                        f"Admin ameghairi Deal Room #{deal_room.id} "
                        f"(tangazo: {deal_room.listing.title}). "
                        f"Sababu: {reason}"
                    ),
                    "en": (
                        f"Admin cancelled Deal Room #{deal_room.id} "
                        f"(listing: {deal_room.listing.title}). "
                        f"Reason: {reason}"
                    ),
                },
            )

        def _notify():
            from .services.notifications import (
                notify_deal_room_cancelled_by_admin,
            )
            notify_deal_room_cancelled_by_admin(
                deal_room=deal_room,
                reason=reason,
                cancelled_by=request.user,
            )

        transaction.on_commit(lambda: _notify_safe(_notify))

        return Response(
            AdminDealRoomSerializer(
                deal_room, context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )