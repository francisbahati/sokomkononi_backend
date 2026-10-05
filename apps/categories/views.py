import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.core.mixins import SoftDeleteViewSetMixin

from .models import Category
from .serializers import CategorySerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


# ============================================================
# AUDIT LOG HELPER
# ============================================================
def _log(request, action, target="", target_id=None, details=""):
    """Helper — ina-logi admin action bila kuvunja request kama log inashindwa."""
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
        import logging
        logging.getLogger(__name__).exception(
            "Failed to write audit log: %s", action,
        )


@extend_schema_view(
    list=extend_schema(
        summary="Orodha ya makundi",
        responses=CategorySerializer(many=True),
    ),
    retrieve=extend_schema(summary="Taarifa za kundi"),
    create=extend_schema(summary="Unda kundi"),
    update=extend_schema(summary="Badilisha kundi"),
    partial_update=extend_schema(summary="Sasisha sehemu ya kundi"),
    destroy=extend_schema(
        summary="Futa kundi",
        responses={
            204: OpenApiResponse(description="Kundi limewekwa kwenye kikapu."),
        },
    ),
)
class CategoryViewSet(SoftDeleteViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    staff_can_restore_any = True

    def get_queryset(self):
        qs = Category.objects.all()
        if (
            self.request.user.is_authenticated
            and self.request.user.is_staff
        ):
            return qs
        return qs.filter(is_active=True)

    def _can_restore(self, instance):
        return bool(self.request.user.is_staff)

    # ══════════════════════════════════════════════════════════
    # CREATE — log category.created
    # ══════════════════════════════════════════════════════════
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)

        if response.status_code == status.HTTP_201_CREATED:
            data = response.data or {}
            _log(
                request,
                action="category.created",
                target="Category",
                target_id=data.get("id"),
                details=(
                    f"Created category: "
                    f"{data.get('name') or data.get('slug') or '—'}"
                ),
            )

        return response

    # ══════════════════════════════════════════════════════════
    # UPDATE — log category.updated
    # ══════════════════════════════════════════════════════════
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_name = instance.name
        response = super().update(request, *args, **kwargs)

        if response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED,
        ):
            _log(
                request,
                action="category.updated",
                target="Category",
                target_id=instance.id,
                details=f"Updated category: {old_name}",
            )

        return response

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        old_name = instance.name
        response = super().partial_update(request, *args, **kwargs)

        if response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_202_ACCEPTED,
        ):
            _log(
                request,
                action="category.updated",
                target="Category",
                target_id=instance.id,
                details=f"Updated category (partial): {old_name}",
            )

        return response

    # ══════════════════════════════════════════════════════════
    # DESTROY — log category.deleted
    # ══════════════════════════════════════════════════════════
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        cat_id = instance.id
        cat_name = instance.name
        cat_slug = instance.slug

        response = super().destroy(request, *args, **kwargs)

        if response.status_code in (
            status.HTTP_204_NO_CONTENT,
            status.HTTP_200_OK,
        ):
            _log(
                request,
                action="category.deleted",
                target="Category",
                target_id=cat_id,
                details=(
                    f"Deleted category: {cat_name} "
                    f"(slug={cat_slug})"
                ),
            )

        return response

    # ══════════════════════════════════════════════════════════
    # UPLOAD IMAGE — (hiari) log category.updated
    # ══════════════════════════════════════════════════════════
    @action(
        detail=False,
        methods=["post"],
        url_path="upload-image",
        url_name="upload-image",
        permission_classes=[permissions.IsAdminUser],
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_image(self, request):
        f = request.FILES.get("image")
        if not f:
            return Response(
                {"detail": "Picha inahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        if f.content_type not in allowed_types:
            return Response(
                {"detail": "Aina ya picha hairuhusiwi. Tumia JPG, PNG au WEBP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if f.size > 5 * 1024 * 1024:
            return Response(
                {"detail": "Picha haiwezi kuzidi 5 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else "jpg"
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        path = default_storage.save(
            f"categories/{uuid.uuid4().hex}.{ext}",
            ContentFile(f.read()),
        )
        url = default_storage.url(path)
        if not url.startswith("http"):
            url = request.build_absolute_uri(url)

        return Response(
            {"image_url": url, "url": url},
            status=status.HTTP_201_CREATED,
        )

    # ══════════════════════════════════════════════════════════
    # REORDER — admin anaweza kupanga categories
    # ══════════════════════════════════════════════════════════
    @action(
        detail=False,
        methods=["post"],
        url_path="reorder",
        url_name="reorder",
        permission_classes=[permissions.IsAdminUser],
    )
    def reorder(self, request):
        """
        Reorder categories.
        Body: { "order": ["key_1", "key_2", ...] }
        au:   { "order": [id_1, id_2, ...] }
        """
        order = request.data.get("order") or []
        if not isinstance(order, list) or not order:
            return Response(
                {"detail": "order lazima iwe list isiyo tupu."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = 0
        for idx, item in enumerate(order):
            cat = None
            # Jaribu id
            if isinstance(item, int) or (isinstance(item, str) and item.isdigit()):
                cat = Category.objects.filter(id=item).first()
            # Jaribu slug
            if not cat:
                cat = Category.objects.filter(slug=item).first()
            # Jaribu name
            if not cat:
                cat = Category.objects.filter(name=item).first()

            if cat:
                cat.ordering = idx
                cat.save(update_fields=["ordering"])
                updated += 1

        _log(
            request,
            action="category.reordered",
            target="Category",
            target_id=None,
            details=f"Reordered {updated} categories",
        )

        return Response({
            "detail": f"Categories {updated} zimepangwa upya.",
            "updated": updated,
        })