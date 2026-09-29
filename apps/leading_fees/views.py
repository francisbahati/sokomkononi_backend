from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.listings.models import Listing

from .models import LeadingFeeConfig, ListingLeading
from .serializers import (
    LeadingApplySerializer,
    LeadingFeeConfigSerializer,
    LeadingPaymentSerializer,
    ListingLeadingSerializer,
)
from .services.leading import create_leading, initiate_leading_payment


class LeadingFeeConfigViewSet(viewsets.GenericViewSet):
    serializer_class = LeadingFeeConfigSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def list(self, request):
        obj, _ = LeadingFeeConfig.objects.get_or_create(pk=1)
        return Response(LeadingFeeConfigSerializer(obj).data)

    def create(self, request):
        obj, _ = LeadingFeeConfig.objects.get_or_create(pk=1)
        serializer = LeadingFeeConfigSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def partial_update(self, request, pk=None):
        obj, _ = LeadingFeeConfig.objects.get_or_create(pk=1)
        serializer = LeadingFeeConfigSerializer(obj, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ListingLeadingViewSet(viewsets.GenericViewSet):
    """
        POST /api/leading-fees/apply/        create PENDING leading
        POST /api/leading-fees/{id}/pay/     mark paid + activate
        GET  /api/leading-fees/mine/         my purchases
        GET  /api/leading-fees/listing/{id}/ public current leading
    """
    serializer_class = ListingLeadingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ListingLeading.objects.select_related("listing", "seller")

    @action(detail=False, methods=["post"], url_path="apply")
    def apply(self, request):
        s = LeadingApplySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        leading = create_leading(
            listing_id=s.validated_data["listing"],
            user=request.user,
            payment_reference=s.validated_data.get("payment_reference", ""),
        )
        return Response(
            ListingLeadingSerializer(leading).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        leading = get_object_or_404(self.get_queryset(), pk=pk)
        if leading.seller_id != request.user.id and not request.user.is_staff:
            return Response({"detail": "Huna ruhusa."}, status=status.HTTP_403_FORBIDDEN)
        data = initiate_leading_payment(
            leading=leading, user=request.user,
            payment_method=request.data.get("payment_method", "mobile"),
            phone=request.data.get("phone", ""),
        )
        return Response({"fimipay": data}, status=status.HTTP_201_CREATED)
        s = LeadingPaymentSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        leading = mark_leading_paid(
            leading=leading,
            payment_reference=s.validated_data["payment_reference"],
        )
        return Response(ListingLeadingSerializer(leading).data)

    @action(detail=False, methods=["get"], url_path="mine")
    def mine(self, request):
        qs = self.get_queryset().filter(seller=request.user)
        return Response(ListingLeadingSerializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path=r"listing/(?P<listing_id>\d+)")
    def listing_leading(self, request, listing_id=None):
        listing = get_object_or_404(Listing, pk=listing_id)
        return Response({
            "listing_id": listing.id,
            "leading_until": listing.leading_until,
        })
