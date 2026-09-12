from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from rest_framework import permissions, viewsets

from .models import Category
from .serializers import CategorySerializer


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Kila mtu anaweza kuona makundi yaliyo hai.
    Admin/staff pekee ndiye anayeruhusiwa kuyaongeza,
    kuyabadilisha au kuyafuta.
    """

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
        description=(
            "Huonyesha makundi ya SokoMkononi. "
            "Watumiaji wa kawaida huona makundi yaliyo hai pekee."
        ),
        responses=CategorySerializer(many=True),
    ),
    retrieve=extend_schema(
        summary="Taarifa za kundi",
        description="Huonyesha taarifa za kundi moja.",
        responses=CategorySerializer,
    ),
    create=extend_schema(
        summary="Unda kundi",
        description="Admin pekee ndiye anayeweza kuunda kundi jipya.",
        request=CategorySerializer,
        responses={
            201: CategorySerializer,
        },
        examples=[
            OpenApiExample(
                "Mfano wa kundi",
                value={
                    "name": "Nyumba & Majengo",
                    "description": (
                        "Nyumba, apartments, ofisi na majengo mbalimbali."
                    ),
                    "is_active": True,
                    "ordering": 1,
                },
                request_only=True,
            ),
        ],
    ),
    update=extend_schema(
        summary="Badilisha kundi",
        description="Admin pekee ndiye anayeweza kubadilisha kundi.",
        request=CategorySerializer,
        responses={
            200: CategorySerializer,
        },
    ),
    partial_update=extend_schema(
        summary="Sasisha sehemu ya kundi",
        description=(
            "Admin anaweza kusasisha sehemu ya taarifa za kundi."
        ),
        request=CategorySerializer,
        responses={
            200: CategorySerializer,
        },
    ),
    destroy=extend_schema(
        summary="Futa kundi",
        description="Admin pekee ndiye anayeweza kufuta kundi.",
        responses={
            204: OpenApiResponse(
                description="Kundi limefutwa.",
            ),
        },
    ),
)
class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        queryset = Category.objects.all()

        if (
            self.request.user.is_authenticated
            and self.request.user.is_staff
        ):
            return queryset

        return queryset.filter(is_active=True)