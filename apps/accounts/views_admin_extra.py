# apps/accounts/views_admin_extra.py
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.deals.models import DealRoom
from apps.listings.models import Listing

from .models import User
from .serializers import ProfileSerializer


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_staff
        )


class AdminUserFullView(APIView):
    """
    GET /api/admin/users/{id}/full/
    Returns user + listings + deal rooms.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        user = User.all_objects.filter(pk=pk).first()
        if not user:
            return Response({"detail": "Haipatikani."}, status=404)

        listings = Listing.objects.filter(seller=user)[:50]
        deals = DealRoom.objects.filter(buyer=user)[:20]
        sells = DealRoom.objects.filter(seller=user)[:20]

        return Response({
            "user": ProfileSerializer(user).data,
            "listings": [
                {
                    "id": l.id,
                    "title": l.title,
                    "price": str(l.price),
                    "status": l.status,
                }
                for l in listings
            ],
            "deals": [
                {
                    "id": d.id,
                    "listingTitle": d.listing.title,
                    "buyerName": d.buyer.name,
                    "sellerName": d.seller.name,
                    "status": d.status,
                    "price": str(d.agreed_price or d.listing.price),
                    "role": "buyer",
                }
                for d in deals
            ] + [
                {
                    "id": d.id,
                    "listingTitle": d.listing.title,
                    "buyerName": d.buyer.name,
                    "sellerName": d.seller.name,
                    "status": d.status,
                    "price": str(d.agreed_price or d.listing.price),
                    "role": "seller",
                }
                for d in sells
            ],
        })
