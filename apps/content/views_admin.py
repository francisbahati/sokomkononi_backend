from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from .models import Banner, FAQ, SiteContent, Testimonial
from .serializers import (
    BannerSerializer,
    FAQSerializer,
    SiteContentSerializer,
    TestimonialSerializer,
)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


MODEL_MAP = {
    "banners": (Banner, BannerSerializer),
    "testimonials": (Testimonial, TestimonialSerializer),
    "faqs": (FAQ, FAQSerializer),
    "site-content": (SiteContent, SiteContentSerializer),
}

SITE_KEY_MAP = {
    "about": "ABOUT",
    "terms": "TERMS",
    "privacy": "PRIVACY",
    "help": "HELP",
}


class AdminContentViewSet(viewsets.GenericViewSet):
    """
    Admin management of content blocks. Reads are public so the
    frontend can fetch banners/testimonials/faqs without auth.
    """

    serializer_class = BannerSerializer  # default for drf-spectacular
    permission_classes = [IsAdminUser]

    def get_permissions(self):
        # Public reads on /banners/, /testimonials/, /faqs/.
        method = getattr(self.request, "method", "")
        if method in ("GET", "HEAD", "OPTIONS"):
            return [permissions.AllowAny()]
        return [IsAdminUser()]

    def _resolve(self, kind):
        return MODEL_MAP.get(kind)

    def list_content(self, request, kind=None):
        pair = self._resolve(kind)
        if not pair:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        Model, Serializer = pair
        return Response(Serializer(Model.objects.all(), many=True).data)

    def create_content(self, request, kind=None):
        pair = self._resolve(kind)
        if not pair:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        Model, Serializer = pair
        serializer = Serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def detail_content(self, request, kind=None, pk=None):
        pair = self._resolve(kind)
        if not pair:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        Model, Serializer = pair
        obj = Model.objects.filter(pk=pk).first()
        if not obj:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "GET":
            return Response(Serializer(obj).data)

        if request.method in ("PATCH", "PUT"):
            serializer = Serializer(
                obj,
                data=request.data,
                partial=(request.method == "PATCH"),
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        if request.method == "DELETE":
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


class AdminSiteContentView(viewsets.GenericViewSet):
    """
    PATCH /api/admin/content/{about,terms,privacy,help}/
    Admin-only update of a SiteContent singleton row.
    """
    serializer_class = SiteContentSerializer
    permission_classes = [IsAdminUser]

    def partial_update(self, request, key=None):
        upper = SITE_KEY_MAP.get((key or "").lower())
        if not upper:
            return Response(
                {"detail": "Sehemu haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        obj, _ = SiteContent.objects.get_or_create(key=upper)
        serializer = SiteContentSerializer(
            obj, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SiteContentSerializer(obj).data)

    def retrieve(self, request, key=None):
        upper = SITE_KEY_MAP.get((key or "").lower())
        if not upper:
            return Response(
                {"detail": "Sehemu haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        obj = SiteContent.objects.filter(key=upper).first()
        if not obj:
            return Response(
                {"detail": "Haipo."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SiteContentSerializer(obj).data)
