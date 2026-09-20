from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from apps.listings.models import Listing

from .models import Conversation, Message
from .serializers import (
    ConversationCreateSerializer,
    ConversationListSerializer,
    ConversationSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)


class ConversationViewSet(viewsets.GenericViewSet):
    """
    Chat threads between buyer and seller about a listing.

        GET     /api/messaging/conversations/            list mine
        POST    /api/messaging/conversations/            create { listing, initial_message }
        GET     /api/messaging/conversations/{id}/       detail
        POST    /api/messaging/conversations/{id}/messages/  send
        POST    /api/messaging/conversations/{id}/read/  mark all read
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Conversation.objects
            .select_related("listing", "buyer", "seller")
            .prefetch_related("messages", "messages__sender")
        )
        if user.is_staff:
            return qs
        return qs.filter(Q(buyer=user) | Q(seller=user))

    def list(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = ConversationListSerializer(
            page if page is not None else qs,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        conv = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(
            ConversationSerializer(conv, context={"request": request}).data,
        )

    @extend_schema(
        request=ConversationCreateSerializer,
        responses={201: ConversationSerializer},
    )
    def create(self, request):
        serializer = ConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        listing = get_object_or_404(
            Listing, pk=serializer.validated_data["listing"],
        )

        if listing.seller_id == request.user.id:
            return Response(
                {"detail": "Huwezi kuanzisha mazungumzo na mwenyewe."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conv, created = Conversation.objects.get_or_create(
            listing=listing,
            buyer=request.user,
            seller=listing.seller,
        )

        initial = serializer.validated_data.get("initial_message", "").strip()
        if initial:
            Message.objects.create(
                conversation=conv,
                sender=request.user,
                text=initial,
            )
            conv.last_message = initial
            conv.last_message_at = timezone.now()
            conv.save(update_fields=["last_message", "last_message_at", "updated_at"])

        return Response(
            ConversationSerializer(conv, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        request=MessageCreateSerializer,
        responses={201: MessageSerializer},
    )
    @action(detail=True, methods=["post"], url_path="messages")
    def send_message(self, request, pk=None):
        conv = get_object_or_404(self.get_queryset(), pk=pk)

        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = Message.objects.create(
            conversation=conv,
            sender=request.user,
            text=serializer.validated_data["text"],
        )

        conv.last_message = message.text
        conv.last_message_at = message.created_at
        conv.save(update_fields=["last_message", "last_message_at", "updated_at"])

        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        conv = get_object_or_404(self.get_queryset(), pk=pk)
        now = timezone.now()
        updated = (
            conv.messages
            .filter(is_read=False)
            .exclude(sender=request.user)
            .update(is_read=True, read_at=now)
        )
        return Response({"updated": updated})