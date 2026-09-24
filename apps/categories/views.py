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
