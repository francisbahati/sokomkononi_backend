from rest_framework import permissions, status, viewsets
from rest_framework.response import Response


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
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


MODEL_MAP = {
    "banners": (Banner, BannerSerializer),
    "testimonials": (Testimonial, TestimonialSerializer),
    "faqs": (FAQ, FAQSerializer),
    "site-content": (SiteContent, SiteContentSerializer),
}


class AdminContentViewSet(viewsets.GenericViewSet):
    """
    Admin-only management of content blocks. `kind` is passed via
    URL kwargs by urls_admin.py.
    """

    permission_classes = [IsAdminUser]

    def _resolve(self, kind):
        return MODEL_MAP.get(kind)

    def _list(self, request, kind=None):
        pair = self._resolve(kind)
        if not pair:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        Model, Serializer = pair
        return Response(Serializer(Model.objects.all(), many=True).data)

    def _create(self, request, kind=None):
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

    def _detail(self, request, kind=None, pk=None):
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
                obj, data=request.data, partial=(request.method == "PATCH"),
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        if request.method == "DELETE":
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
