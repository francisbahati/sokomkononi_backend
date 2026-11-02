# apps/verifications/views.py

import logging

from django.db import transaction
from django.db.models import Exists, OuterRef
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
        GET     /api/verifications/{id}/documents/{doc_id}/stream  bytes
        POST    /api/verifications/{id}/documents/     multipart upload
        DELETE  /api/verifications/{id}/               owner or admin
    """

    serializer_class = VerificationRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_throttles(self):
        if self.action == "create":
            # Guard: usiweke scope kama haipo kwenye settings —
            # vinginevyo DRF inatupa KeyError.
            scope = "verification_request"
            try:
                from django.conf import settings
                rates = getattr(settings, "DEFAULT_THROTTLE_RATES", {}) or {}
                if scope in rates:
                    self.throttle_scope = scope
                else:
                    self.throttle_scope = None
            except Exception:
                self.throttle_scope = None
        else:
            self.throttle_scope = None
        return super().get_throttles()

    def get_queryset(self):
        user = self.request.user
        qs = (
            VerificationRequest.objects
            # ✅ user__preferences: inahitajika na notify._user_lang()
            #    ili kuepuka N+1 wakati notifications zinatumwa kwenye list
            .select_related("user", "user__preferences", "reviewed_by")
            .prefetch_related("documents")
        )
        if not user.is_staff:
            qs = qs.filter(user=user)

        # ✅ Annotate roles ili kuepuka N+1 kwenye serializer.
        # Kama apps.listings / apps.deals hazipo (mfano wakati wa tests),
        # tunaacha queryset bila annotations — serializer itafanya fallback.
        try:
            from apps.listings.models import Listing
            from apps.deals.models import DealRoom

            qs = qs.annotate(
                has_listings=Exists(
                    Listing.objects.filter(
                        seller=OuterRef("user"), is_deleted=False,
                    )
                ),
                has_deals=Exists(
                    DealRoom.objects.filter(buyer=OuterRef("user"))
                ),
            )
        except Exception:
            logger.exception(
                "[verifications] failed to annotate roles for queryset",
            )

        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return VerificationCreateSerializer
        if self.action == "reject":
            return VerificationRejectSerializer
        if self.action == "document_url":
            return VerificationDocumentSerializer
        return VerificationRequestSerializer

    # ══════════════════════════════════════════════════════════
    # LIST
    # ══════════════════════════════════════════════════════════
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

    # ══════════════════════════════════════════════════════════
    # RETRIEVE
    # ══════════════════════════════════════════════════════════
    def retrieve(self, request, pk=None):
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        return Response(
            VerificationRequestSerializer(
                obj, context={"request": request},
            ).data,
        )

    # ══════════════════════════════════════════════════════════
    # CREATE
    # ══════════════════════════════════════════════════════════
    @extend_schema(
        request=VerificationCreateSerializer,
        responses={201: VerificationRequestSerializer},
    )
    def create(self, request):
        serializer = VerificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Kuzuia maombi mawili ya PENDING ya aina moja kwa mtumiaji mmoja.
        # UniqueConstraint kwenye DB inalinda, lakini hapa tunatoa
        # error nzuri kwa mtumiaji badala ya IntegrityError.
        existing = VerificationRequest.objects.filter(
            user=request.user,
            type=data["type"],
            status=VerificationRequest.Status.PENDING,
        ).exists()
        if existing:
            return Response(
                {
                    "detail": (
                        "Una ombi la PENDING la aina hii tayari. "
                        "Subiri likamilike kabla ya kuunda lingine."
                    ),
                    "code": "pending_verification_exists",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        obj = VerificationRequest.objects.create(
            type=data["type"],
            subject=data["subject"],
            subject_id=data.get("subject_id"),
            notes=data.get("notes", ""),
            user=request.user,
            user_name=getattr(request.user, "name", "") or "",
            user_email=getattr(request.user, "email", "") or "",
        )

        # ✅ Audit trail
        _log(
            request,
            action="verification.created",
            target="VerificationRequest",
            target_id=obj.id,
            params={
                "type": obj.type,
                "subject": obj.subject,
            },
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

        # ✅ Atomic: status + is_verified + notifications kwa pamoja
        with transaction.atomic():
            obj.status = VerificationRequest.Status.APPROVED
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
            obj.save(update_fields=[
                "status", "reviewed_by", "reviewed_at", "updated_at",
            ])

            try:
                target_user = obj.user
                if obj.type in (
                    VerificationRequest.Type.SELLER,
                    VerificationRequest.Type.BUYER,
                ):
                    target_user.is_verified = True
                    target_user.save(
                        update_fields=["is_verified", "updated_at"],
                    )
                    logger.info(
                        "[verifications] user %s marked as verified "
                        "(type=%s)", target_user.id, obj.type,
                    )
            except Exception as exc:
                logger.warning(
                    "[verifications] failed to update user.is_verified "
                    "for request %s: %s", obj.id, exc,
                )

            _log(
                request,
                action="verification.approved",
                target="VerificationRequest",
                target_id=obj.id,
                params={"name": f"{obj.type} - {obj.subject}"},
            )

            # on_commit ndani ya atomic — itasubiri commit halisi
            notify_approved(obj)

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
        reason = serializer.validated_data["rejection_reason"]

        with transaction.atomic():
            obj.status = VerificationRequest.Status.REJECTED
            obj.rejection_reason = reason
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
                params={
                    "name": f"{obj.type} - {obj.subject}",
                    "reason": reason[:200],
                },
            )

            notify_rejected(obj, reason)

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

        with transaction.atomic():
            obj.documents_requested_at = timezone.now()
            obj.documents_request_message = message
            obj.save(update_fields=[
                "documents_requested_at",
                "documents_request_message",
                "updated_at",
            ])

            _log(
                request,
                action="verification.documents_requested",
                target="VerificationRequest",
                target_id=obj.id,
                params={
                    "name": f"{obj.type} - {obj.subject}",
                    "message": message[:200],
                },
            )

            notify_documents_requested(obj, message)

        return Response(
            VerificationRequestSerializer(
                obj, context={"request": request},
            ).data,
        )

    # ══════════════════════════════════════════════════════════
    # DOCUMENT STREAM — bytes kupitia Django
    # ══════════════════════════════════════════════════════════
    @action(
        detail=True, methods=["get"],
        url_path="documents/(?P<doc_id>[^/.]+)/stream",
    )
    def stream_document(self, request, pk=None, doc_id=None):
        """
        Stream the document bytes through Django — bypasses S3 XML errors.

        Auth: standard DRF auth (Authorization: Bearer <jwt>).

        Inajaribu storage mbili kwa mpangilio:
          1. `default_storage` (CloudflareR2MediaStorage)
          2. `doc.file.storage` (PrivateR2Storage)
          3. local MEDIA_ROOT (fallback ya legacy)

        Returns:
          - 200 + FileResponse on success
          - 404 + JSON {code: "file_missing"} when file is gone
        """
        import mimetypes
        from pathlib import Path
        from django.conf import settings as dj_settings
        from django.core.files.storage import default_storage
        from django.http import FileResponse, Http404

        obj = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            doc = obj.documents.get(pk=doc_id)
        except VerificationDocument.DoesNotExist:
            raise Http404("Document not found")

        if not doc.file:
            return Response(
                {"ok": False, "code": "file_missing",
                 "detail": "Document haina faili."},
                status=status.HTTP_404_NOT_FOUND,
            )

        file_name = doc.file.name
        content_type, _ = mimetypes.guess_type(file_name)
        content_type = content_type or "application/octet-stream"

        def _make_response(handle, storage_label):
            response = FileResponse(handle, content_type=content_type)
            response["Content-Disposition"] = (
                f'inline; filename="{file_name.split("/")[-1]}"'
            )
            response["Cache-Control"] = "private, max-age=300"
            response["X-Storage"] = storage_label
            return response

        # ── 1. default_storage (CloudflareR2MediaStorage) ──
        try:
            if default_storage.exists(file_name):
                f = default_storage.open(file_name, "rb")
                # ✅ Audit trail ya ufikiaji wa document nyeti
                _log(
                    request,
                    action="verification.document_streamed",
                    target="VerificationDocument",
                    target_id=doc.pk,
                    params={"storage": "default"},
                )
                return _make_response(f, "default")
        except Exception:
            logger.exception(
                "[verifications] stream via default_storage failed "
                "for doc %s", doc.pk,
            )

        # ── 2. doc.file.storage (PrivateR2Storage) ──
        try:
            if doc.file.storage.exists(file_name):
                f = doc.file.storage.open(file_name, "rb")
                _log(
                    request,
                    action="verification.document_streamed",
                    target="VerificationDocument",
                    target_id=doc.pk,
                    params={"storage": "private"},
                )
                return _make_response(f, "private")
        except Exception:
            logger.exception(
                "[verifications] stream via doc.file.storage failed "
                "for doc %s", doc.pk,
            )

        # ── 3. local MEDIA_ROOT (legacy fallback) ──
        try:
            local_path = Path(str(dj_settings.MEDIA_ROOT)) / file_name
            if local_path.exists() and local_path.is_file():
                _log(
                    request,
                    action="verification.document_streamed",
                    target="VerificationDocument",
                    target_id=doc.pk,
                    params={"storage": "local"},
                )
                return _make_response(open(local_path, "rb"), "local")
        except Exception:
            logger.exception(
                "[verifications] local fallback failed for doc %s", doc.pk,
            )

        # ── 4. Haipatikani ──
        return Response(
            {"ok": False, "code": "file_missing",
             "document_id": doc.pk,
             "detail": "Faili haipatikani kwenye hifadhi. "
                       "Huenda ilifutwa au haikupakiwa."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # ══════════════════════════════════════════════════════════
    # DOCUMENT URL — signed URL mpya (legacy; bado inatumika)
    # ══════════════════════════════════════════════════════════
    @action(
        detail=True, methods=["get"],
        url_path="documents/(?P<doc_id>[^/.]+)",
    )
    def document_url(self, request, pk=None, doc_id=None):
        """
        Rudisha signed URL mpya kwa document fulani.

        GET /api/verifications/{request_id}/documents/{doc_id}/
        """
        obj = get_object_or_404(self.get_queryset(), pk=pk)
        try:
            doc = obj.documents.get(pk=doc_id)
        except VerificationDocument.DoesNotExist:
            return Response(
                {"detail": "Document haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check the file exists BEFORE returning a signed URL.
        if doc.file:
            from django.core.files.storage import default_storage
            _exists = False
            try:
                if default_storage.exists(doc.file.name):
                    _exists = True
            except Exception:
                logger.exception(
                    "[verifications] default_storage.exists() failed "
                    "for doc %s", doc.pk,
                )
            if not _exists:
                try:
                    _exists = doc.file.storage.exists(doc.file.name)
                except Exception:
                    logger.exception(
                        "[verifications] doc.file.storage.exists() failed "
                        "for doc %s", doc.pk,
                    )
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
                status=status.HTTP_400_BAD_REQUEST,
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
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # ✅ Soma header mara moja, kisha seek(0)
            header = f.read(5)
            f.seek(0)
            if header != b"%PDF-":
                return Response(
                    {"detail": "Faili si PDF halali."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            ok, err = validate_image(
                f, max_bytes=10 * 1024 * 1024, field="file",
            )
            if not ok:
                return Response(
                    {"detail": err},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        doc = VerificationDocument.objects.create(
            request=obj,
            file=f,
            name=f.name[:255],
        )

        # ✅ Audit trail
        _log(
            request,
            action="verification.document_uploaded",
            target="VerificationDocument",
            target_id=doc.pk,
            params={
                "request_id": obj.id,
                "filename": doc.name,
                "size": getattr(f, "size", None),
                "content_type": f.content_type,
            },
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

        # ✅ Audit kabla ya soft-delete (baada ya delete, obj bado ipo
        # lakini is_deleted=True; tunataka log iwe na id)
        _log(
            request,
            action="verification.deleted",
            target="VerificationRequest",
            target_id=obj.id,
            params={
                "name": f"{obj.type} - {obj.subject}",
                "status": obj.status,
                "by": "admin" if request.user.is_staff else "owner",
            },
        )

        obj.delete(by=request.user, reason="Verification request removed")
        return Response(
            {"detail": "Ombi limewekwa kwenye kikapu."},
            status=status.HTTP_200_OK,
        )