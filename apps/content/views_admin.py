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


class AdminContentViewSet(viewsets.GenericViewSet):
    """
    Admin-only management of content blocks.

        GET     /api/admin/content/banners/
        POST    /api/admin/content/banners/
        PATCH   /api/admin/content/banners/{id}/
        DELETE  /api/admin/content/banners/{id}/

        ...same pattern for testimonials, faqs, site-content
    """

    permission_classes = [IsAdminUser]

    def _model_serializer(self, kind):
        return {
            "banners": (Banner, BannerSerializer),
            "testimonials": (Testimonial, TestimonialSerializer),
            "faqs": (FAQ, FAQSerializer),
            "site-content": (SiteContent, SiteContentSerializer),
        }.get(kind)

    def _list(self, request, kind):
        pair = self._model_serializer(kind)
        if not pair:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        Model, Serializer = pair
        qs = Model.objects.all()
        return Response(Serializer(qs, many=True).data)

    def _create(self, request, kind):
        pair = self._model_serializer(kind)
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

    def _detail(self, request, kind, pk, method):
        pair = self._model_serializer(kind)
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
        if method == "get":
            return Response(Serializer(obj).data)
        if method == "patch":
            serializer = Serializer(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        if method == "delete":
            obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)