from django.db.models import Q
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import BannerAd
from .serializers import BannerAdCreateSerializer, BannerAdSerializer
from .services import create_banner_ad


class BannerAdViewSet(viewsets.GenericViewSet):
    """
        GET     /api/banners/                list active (public)
        GET     /api/banners/mine/           seller's own banners
        GET     /api/banners/all/            admin: all banners
        POST    /api/banners/                create { listing, payment_reference? }
        DELETE  /api/banners/{id}/           seller or admin
    """

    serializer_class = BannerAdSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = BannerAd.objects.select_related("listing", "seller")
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return qs
        if self.request.user.is_authenticated:
            return qs.filter(Q(active=True) | Q(seller=self.request.user))
        return qs.filter(active=True)

    def list(self, request):
        now = timezone.now()
        qs = self.get_queryset().filter(active=True, expires_at__gt=now)
        return Response(BannerAdSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        qs = BannerAd.objects.filter(seller=request.user)
        return Response(BannerAdSerializer(qs, many=True).data)

    @action(
        detail=False, methods=["get"], url_path="all",
        permission_classes=[permissions.IsAdminUser],
    )
    def all_banners(self, request):
        return Response(BannerAdSerializer(self.get_queryset(), many=True).data)

    def create(self, request):
        serializer = BannerAdCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        banner = create_banner_ad(
            listing_id=serializer.validated_data["listing"],
            seller=request.user,
            payment_reference=serializer.validated_data.get(
                "payment_reference", ""
            ),
        )
        return Response(
            BannerAdSerializer(banner).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, pk=None):
        banner = BannerAd.objects.filter(pk=pk).first()
        if not banner:
            return Response(
                {"detail": "Haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if banner.seller_id != request.user.id and not request.user.is_staff:
            return Response(
                {"detail": "Huna ruhusa."},
                status=status.HTTP_403_FORBIDDEN,
            )
        banner.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
