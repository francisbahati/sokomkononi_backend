# apps/verifications/views.py
import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from apps.core.permissions import IsAdminUser
from .models import VerificationDocument, VerificationRequest
from .notify import (
    notify_approved,
    notify_documents_requested,
    notify_rejected,
)
from .serializers import (
    VerificationCreateSerializer,
    VerificationDocumentSerializer,
    VerificationRejectSerializer,
    VerificationRequestSerializer,
)

logger = logging.getLogger(__name__)


def _log(request, action, target="", target_id=None, details=""):
    try:
        from apps.audit.services.audit import log_action
        log_action(
            request=request,
            action=action,
            target=target,
            target_id=target_id,
            details=details,
        )
    except Exception:
        logger.exception("audit failed: %s", action)


class VerificationViewSet(viewsets.GenericViewSet):
    """
    User verification requests (SELLER, BUYER only).

        GET     /api/verifications/                    admin: all, user: own
        GET     /api/verifications/?status=PENDING
        GET     /api/verifications/?type=SELLER
        GET     /api/verifications/{id}/
        POST    /api/verifications/                    create (any authenticated)
        POST    /api/verifications/{id}/approve/       admin only
        POST    /api/verifications/{id}/reject/        admin only
        POST    /api/verifications/{id}/request-documents/  admin only
        GET     /api/verifications/{id}/documents/{doc_id}/  signed URL mpya
        POST    /api/verifications/{id}/documents/     multipart upload
        DELETE  /api/verifications/{id}/               owner or admin
    """

    serializer_class = VerificationRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "verification_request"
        else:
            self.throttle_scope = None
        return super().get_throttles()

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

    def get_serializer_class(self):
        if self.action == "create":
            return VerificationCreateSerializer
        if self.action == "reject":
            return VerificationRejectSerializer
        if self.action == "document_url":
            return VerificationDocumentSerializer
        return VerificationRequestSerializer

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

    # ══════════════════════════════════════════════════════════
    # APPROVE
    # ══════════════════════════════════════════════════════════
    @action(
        detail=True, methods=["post"], url_path="approve",
        permission_classes=[IsAdminUser],
    )
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

        # is_verified — inaruhusu seller NA buyer
        try:
            target_user = obj.user
            if obj.type in (
                VerificationRequest.Type.SELLER,
                VerificationRequest.Type.BUYER,
            ):
                target_user.is_verified = True
                target_user.save(update_fields=["is_verified", "updated_at"])
                logger.info(
                    "[verifications] user %s marked as verified (type=%s)",
                    target_user.id, obj.type,
                )
        except Exception as exc:
            logger.warning(
                "[verifications] failed to update user.is_verified for "
                "request %s: %s", obj.id, exc,
            )

        _log(
            request,
            action="verification.approved",
            target="VerificationRequest",
            target_id=obj.id,
            details=f"Approved: type={obj.type}, subject={obj.subject}",
        )

        try:
            notify_approved(obj)
        except Exception:
            logger.exception("notify_approved failed for %s", obj.id)

        return Response(
            VerificationRequestSerializer(
                obj, context={"request": request},
            ).data,
        )

    # ══════════════════════════════════════════════════════════
    # REJECT
    # ══════════════════════════════════════════════════════════
    @extend_schema(
        request=VerificationRejectSerializer,
        responses={200: VerificationRequestSerializer},
    )
    @action(
        detail=True, methods=["post"], url_path="reject",
        permission_classes=[IsAdminUser],
    )
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

        _log(
            request,
            action="verification.rejected",
            target="VerificationRequest",
            target_id=obj.id,
            details=(
                f"Rejected: "
                f"{serializer.validated_data['rejection_reason'][:200]}"
            ),
        )

        try:
            notify_rejected(
                obj,
                serializer.validated_data["rejection_reason"],
            )
        except Exception:
            logger.exception("notify_rejected failed for %s", obj.id)

        return Response(
            VerificationRequestSerializer(
                obj, context={"request": request},
            ).data,
        )

    # ══════════════════════════════════════════════════════════
    # ADMIN: request documents zaidi
    # ══════════════════════════════════════════════════════════
    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            }
        },
        responses={200: VerificationRequestSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="request-documents",
        permission_classes=[IsAdminUser],
    )
    def request_documents(self, request, pk=None):
        """Admin anaomba mtumiaji apakie documents zaidi."""
        obj = get_object_or_404(VerificationRequest, pk=pk)
        if obj.status != VerificationRequest.Status.PENDING:
            return Response(
                {"detail": "Ombi hili halipo kwenye hali ya PENDING."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = (request.data.get("message") or "").strip()
        if not message:
            return Response(
                {"detail": "Ujumbe unahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        obj.documents_requested_at = timezone.now()
        obj.documents_request_message = message
        obj.save(update_fields=[
            "documents_requested_at",
            "documents_request_message",
            "updated_at",
        ])

        try:
            notify_documents_requested(obj, message)
        except Exception:
            logger.exception(
                "notify_documents_requested failed for %s", obj.id,
            )

        return Response(
            VerificationRequestSerializer(
                obj, context={"request": request},
            ).data,
        )

    # ══════════════════════════════════════════════════════════
    # DOCUMENT URL — signed URL mpya (kwa admin preview)
    # ══════════════════════════════════════════════════════════
    @action(
        detail=True, methods=["get"],
        url_path="documents/(?P<doc_id>[^/.]+)",
    )
    def document_url(self, request, pk=None, doc_id=None):
        """
        Rudisha signed URL mpya kwa document fulani.

        GET /api/verifications/{request_id}/documents/{doc_id}/

        Signed URLs zinaisha baada ya SIGNED_URL_EXPIRY, kwa hiyo admin
        anahitaji kupata URL mpya kila mara anapofungua document.
        """
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            doc = obj.documents.get(pk=doc_id)
        except VerificationDocument.DoesNotExist:
            return Response(
                {"detail": "Document haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check the file exists in R2/S3 BEFORE returning a signed URL.
        # Prevents the frontend opening an S3 <NoSuchKey> XML page.
        if doc.file:
            try:
                _exists = doc.file.storage.exists(doc.file.name)
            except Exception:
                logger.exception("[verifications] storage.exists() failed for doc %s", doc.pk)
                _exists = True
            if not _exists:
                return Response(
                    {"ok": False, "file_missing": True,
                     "code": "file_missing",
                     "document_id": doc.pk,
                     "detail": "Faili haipatikani kwenye hifadhi. "
                               "Huenda ilifutwa au haikupakiwa."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        serializer = VerificationDocumentSerializer(
            doc, context={"request": request},
        )
        return Response(serializer.data)

    # ══════════════════════════════════════════════════════════
    # UPLOAD document
    # ══════════════════════════════════════════════════════════
    @action(
        detail=True, methods=["post"], url_path="documents",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_document(self, request, pk=None):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        if obj.status != VerificationRequest.Status.PENDING:
            return Response(
                {"detail": "Ombi hili halipokei nyaraka mpya."},
                status=400,
            )
        f = request.FILES.get("file")
        if not f:
            return Response(
                {"detail": "Faili linahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.core.image_utils import validate_image
        if f.content_type == "application/pdf":
            if f.size > 10 * 1024 * 1024:
                return Response(
                    {"detail": "Faili haiwezi kuzidi 10MB."},
                    status=400,
                )
            if not (f.read(5) == b"%PDF-"):
                f.seek(0)
                return Response(
                    {"detail": "Faili si PDF halali."}, status=400,
                )
            f.seek(0)
        else:
            ok, err = validate_image(
                f, max_bytes=10 * 1024 * 1024, field="file",
            )
            if not ok:
                return Response({"detail": err}, status=400)

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

    # ══════════════════════════════════════════════════════════
    # DELETE
    # ══════════════════════════════════════════════════════════
    def destroy(self, request, pk=None):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        if obj.user_id != request.user.id and not request.user.is_staff:
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )
        obj.delete(by=request.user, reason="Verification request removed")
        return Response(
            {"detail": "Ombi limewekwa kwenye kikapu."},
            status=status.HTTP_200_OK,
        )