from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Bundle, BundlePurchase
from .serializers import (
    BundlePurchaseCreateSerializer,
    BundlePurchaseSerializer,
    BundleSerializer,
)
from .services import create_purchase, mark_purchase_paid


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class BundleViewSet(viewsets.ModelViewSet):
    """
        GET     /api/bundles/                  list active bundles (public)
        POST    /api/bundles/                  admin create
        GET     /api/bundles/{id}/
        PATCH   /api/bundles/{id}/             admin
        DELETE  /api/bundles/{id}/             admin
    """

    serializer_class = BundleSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = Bundle.objects.all()
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return qs
        return qs.filter(active=True)

    def list(self, request):
        qs = self.get_queryset()
        type_filter = request.query_params.get("type")
        if type_filter:
            qs = qs.filter(type=type_filter.upper())
        page = self.paginate_queryset(qs)
        serializer = BundleSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class BundlePurchaseViewSet(viewsets.GenericViewSet):
    """
        GET     /api/bundles/purchases/           my purchases
        POST    /api/bundles/purchases/           create { bundle, payment_reference? }
        POST    /api/bundles/purchases/{id}/pay/  confirm payment
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = BundlePurchase.objects.select_related("bundle")
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)

    def list(self, request):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = BundlePurchaseSerializer(
            page if page is not None else qs, many=True,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def create(self, request):
        serializer = BundlePurchaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase = create_purchase(
            user=request.user,
            bundle=serializer.validated_data["bundle"],
            payment_reference=serializer.validated_data.get(
                "payment_reference", ""
            ),
        )
        return Response(
            BundlePurchaseSerializer(purchase).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        purchase = self.get_object()
        if purchase.user_id != request.user.id and not request.user.is_staff:
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )
        purchase = mark_purchase_paid(
            purchase=purchase,
            payment_reference=request.data.get("payment_reference", ""),
        )
        return Response(BundlePurchaseSerializer(purchase).data)
