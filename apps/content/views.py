from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from .models import Banner, FAQ, SiteContent, Testimonial
from .serializers import (
    BannerSerializer,
    FAQSerializer,
    SiteContentSerializer,
    TestimonialSerializer,
)


KEY_MAP = {
    "about": "ABOUT",
    "terms": "TERMS",
    "privacy": "PRIVACY",
    "help": "HELP",
}


class ContentViewSet(GenericViewSet):
    """
        GET     /api/content/                   all public content
        GET     /api/content/<key>/             one section
        PATCH   /api/content/<key>/             admin update
    """

    permission_classes = [permissions.AllowAny]

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

    def by_key(self, request, key=None):
        upper = KEY_MAP.get((key or "").lower())
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

    def update_key(self, request, key=None):
        if not (request.user and request.user.is_authenticated and request.user.is_staff):
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )
        upper = KEY_MAP.get((key or "").lower())
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

    def _site_content(self, key):
        obj = SiteContent.objects.filter(key=key).first()
        if not obj:
            return None
        return SiteContentSerializer(obj).data
