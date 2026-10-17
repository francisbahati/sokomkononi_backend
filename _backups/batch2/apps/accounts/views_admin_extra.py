# apps/accounts/views_admin_extra.py
from django.db.models import Q

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.deals.models import DealRoom
from apps.listings.models import Listing

from .models import User
from .serializers import AdminUserSerializer, ProfileSerializer


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
    Returns user + listings + deal rooms (buyer + seller).

    Deals zinatumia Q(buyer=user) | Q(seller=user) ili kuepuka
    duplicates, na kila deal ina `role` ("buyer" au "seller").
    """
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        user = User.all_objects.filter(pk=pk).first()
        if not user:
            return Response(
                {"detail": "Haipatikani."},
                status=404,
            )

        listings = (
            Listing.objects
            .filter(seller=user, is_deleted=False)
            .select_related("category")
            .order_by("-created_at")[:50]
        )

        deal_qs = (
            DealRoom.objects
            .filter(Q(buyer=user) | Q(seller=user))
            .select_related("listing", "buyer", "seller")
            .distinct()
            .order_by("-updated_at")[:40]
        )

        deals_payload = []
        for d in deal_qs:
            role = "buyer" if d.buyer_id == user.id else "seller"
            counterparty = d.seller if role == "buyer" else d.buyer
            deals_payload.append({
                "id": d.id,
                "listingTitle": d.listing.title if d.listing else "—",
                "counterpartyName": counterparty.name if counterparty else "—",
                "buyerName": d.buyer.name if d.buyer else "—",
                "sellerName": d.seller.name if d.seller else "—",
                "status": d.status,
                "price": str(d.agreed_price or (d.listing.price if d.listing else 0)),
                "role": role,
            })

        return Response({
            "user": AdminUserSerializer(user, context={"request": request}).data,
            "profile": ProfileSerializer(user).data,
            "listings": [
                {
                    "id": l.id,
                    "title": l.title,
                    "price": str(l.price),
                    "status": l.status,
                    "category": (
                        l.category.slug if l.category else None
                    ),
                }
                for l in listings
            ],
            "deals": deals_payload,
        })