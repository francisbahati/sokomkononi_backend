from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import ContactMessage
from .serializers import (
    ContactCreateSerializer,
    ContactMessageSerializer,
    ContactReplySerializer,
)


class ContactViewSet(viewsets.GenericViewSet):
    """
        POST    /api/contact/                public: submit message
        GET     /api/contact/                admin: list
        GET     /api/contact/{id}/           admin
        POST    /api/contact/{id}/reply/     admin
        DELETE  /api/contact/{id}/           admin
    """

    serializer_class = ContactMessageSerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        return ContactMessage.objects.all().order_by("-created_at")

    def list(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = ContactMessageSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def create(self, request):
        serializer = ContactCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ContactMessage.objects.create(**serializer.validated_data)
        return Response(
            {
                "detail": (
                    "Ujumbe wako umepokelewa. "
                    "Tutawasiliana nawe hivi karibuni."
                )
            },
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, pk=None):
        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ContactMessageSerializer(obj).data)

    @action(detail=True, methods=["post"], url_path="reply")
    def reply(self, request, pk=None):
        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ContactReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        obj.status = ContactMessage.Status.REPLIED
        obj.replied_by = request.user
        obj.reply_note = serializer.validated_data.get("reply_note", "")
        obj.replied_at = timezone.now()
        obj.save(update_fields=[
            "status", "replied_by", "reply_note", "replied_at",
        ])
        return Response(ContactMessageSerializer(obj).data)

    def destroy(self, request, pk=None):
        obj = self.get_queryset().filter(pk=pk).first()
        if not obj:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
