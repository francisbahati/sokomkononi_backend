from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from .models import VerificationDocument, VerificationRequest
from .serializers import (
    VerificationCreateSerializer,
    VerificationRejectSerializer,
    VerificationRequestSerializer,
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class VerificationViewSet(viewsets.GenericViewSet):
    """
    Verification requests.

        GET     /api/verifications/                    admin: all, user: own
        GET     /api/verifications/?status=PENDING
        GET     /api/verifications/?type=SELLER
        GET     /api/verifications/{id}/
        POST    /api/verifications/                    create (any authenticated)
        POST    /api/verifications/{id}/approve/       admin only
        POST    /api/verifications/{id}/reject/        admin only
        POST    /api/verifications/{id}/documents/     multipart upload
        DELETE  /api/verifications/{id}/               owner or admin
    """

    serializer_class = VerificationRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        qs = (
            VerificationRequest.objects
            .select_related("user", "reviewed_by")
            .prefetch_related("documents")
        )
        if user.is_staff:
            return qs
        return qs.filter(user=user)

    def list(self, request):
        qs = self.get_queryset()
        status_filter = request.query_params.get("status")
        type_filter = request.query_params.get("type")
        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if type_filter:
            qs = qs.filter(type=type_filter.upper())
        page = self.paginate_queryset(qs)
        serializer = VerificationRequestSerializer(
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
            VerificationRequestSerializer(
                obj, context={"request": request},
            ).data,
        )

    @extend_schema(
        request=VerificationCreateSerializer,
        responses={201: VerificationRequestSerializer},
    )
    def create(self, request):
        serializer = VerificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        obj = VerificationRequest.objects.create(
            type=data["type"],
            subject=data["subject"],
            subject_id=data.get("subject_id"),
            notes=data.get("notes", ""),
            user=request.user,
            user_name=request.user.name,
            user_email=request.user.email or "",
        )

        return Response(
            VerificationRequestSerializer(
                obj, context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="approve",
            permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        obj = get_object_or_404(VerificationRequest, pk=pk)
        if obj.status != VerificationRequest.Status.PENDING:
            return Response(
                {"detail": "Ombi hili halipo kwenye hali ya PENDING."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj.status = VerificationRequest.Status.APPROVED
        obj.reviewed_by = request.user
        obj.reviewed_at = timezone.now()
        obj.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "updated_at",
        ])
        return Response(
            VerificationRequestSerializer(
                obj, context={"request": request},
            ).data,
        )

    @extend_schema(
        request=VerificationRejectSerializer,
        responses={200: VerificationRequestSerializer},
    )
    @action(detail=True, methods=["post"], url_path="reject",
            permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        obj = get_object_or_404(VerificationRequest, pk=pk)
        if obj.status != VerificationRequest.Status.PENDING:
            return Response(
                {"detail": "Ombi hili halipo kwenye hali ya PENDING."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = VerificationRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj.status = VerificationRequest.Status.REJECTED
        obj.rejection_reason = serializer.validated_data["rejection_reason"]
        obj.reviewed_by = request.user
        obj.reviewed_at = timezone.now()
        obj.save(update_fields=[
            "status", "rejection_reason", "reviewed_by",
            "reviewed_at", "updated_at",
        ])
        return Response(
            VerificationRequestSerializer(
                obj, context={"request": request},
            ).data,
        )

    @action(
        detail=True, methods=["post"], url_path="documents",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_document(self, request, pk=None):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        f = request.FILES.get("file")
        if not f:
            return Response(
                {"detail": "Faili linahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        doc = VerificationDocument.objects.create(
            request=obj,
            file=f,
            name=f.name[:255],
        )
        return Response(
            {
                "id": doc.id,
                "name": doc.name,
                "uploaded_at": doc.uploaded_at,
            },
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, pk=None):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        if obj.user_id != request.user.id and not request.user.is_staff:
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)