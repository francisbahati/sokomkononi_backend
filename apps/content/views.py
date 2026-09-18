from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


from .models import Banner, FAQ, SiteContent, Testimonial
from .serializers import (
    BannerSerializer,
    FAQSerializer,
    SiteContentSerializer,
    TestimonialSerializer,
)


class ContentViewSet(viewsets.GenericViewSet):
    """
    A single endpoint that returns all public content blocks.

        GET /api/content/                       all content
        GET /api/content/about/
        GET /api/content/terms/
        GET /api/content/privacy/
        GET /api/content/help/
    """

    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["get"], url_path="(?P<key>[a-z]+)")
    def by_key(self, request, key=None):
        return self._key_response(key)

    def list(self, request):
        return Response({
            "banners": BannerSerializer(
                Banner.objects.filter(active=True), many=True,
            ).data,
            "testimonials": TestimonialSerializer(
                Testimonial.objects.filter(active=True), many=True,
            ).data,
            "faqs": FAQSerializer(
                FAQ.objects.filter(active=True), many=True,
            ).data,
            "about": self._site_content("ABOUT"),
            "terms": self._site_content("TERMS"),
            "privacy": self._site_content("PRIVACY"),
            "help": self._site_content("HELP"),
        })

    def _site_content(self, key):
        obj = SiteContent.objects.filter(key=key).first()
        if not obj:
            return None
        return SiteContentSerializer(obj).data

    def _key_response(self, key):
        mapping = {
            "about": "ABOUT",
            "terms": "TERMS",
            "privacy": "PRIVACY",
            "help": "HELP",
        }
        upper = mapping.get((key or "").lower())
        if not upper:
            return Response(
                {"detail": "Sehemu haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = self._site_content(upper)
        if data is None:
            return Response(
                {"detail": "Haipo."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(data)