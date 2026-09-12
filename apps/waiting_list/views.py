from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import WaitingListEntry
from .serializers import (
    WaitingListCreateSerializer,
    WaitingListEntrySerializer,
)
from .services.waiting_list import (
    join_waiting_list,
    leave_waiting_list,
)


class IsVerifiedWaitingListUser(permissions.BasePermission):
    message = (
        "Akaunti yako lazima iwe active na imethibitishwa "
        "ili kutumia waiting list."
    )

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_verified
        )


class WaitingListViewSet(viewsets.GenericViewSet):
    queryset = (
        WaitingListEntry.objects
        .select_related(
            "listing",
            "listing__category",
            "buyer",
        )
    )

    http_method_names = [
        "get",
        "post",
        "delete",
        "head",
        "options",
    ]

    permission_classes = [
        permissions.IsAuthenticated,
        IsVerifiedWaitingListUser,
    ]

    def get_queryset(self):
        user = self.request.user

        queryset = self.queryset

        if user.is_staff:
            return queryset

        return queryset.filter(
            Q(buyer=user)
            | Q(listing__seller=user)
        )

    def get_serializer_class(self):
        if self.action == "create":
            return WaitingListCreateSerializer

        return WaitingListEntrySerializer

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        serializer = WaitingListEntrySerializer(
            queryset,
            many=True,
        )

        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        entry = self.get_object()

        serializer = WaitingListEntrySerializer(entry)

        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = WaitingListCreateSerializer(
            data=request.data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)

        entry = join_waiting_list(
            listing=serializer.validated_data["listing"],
            buyer=request.user,
        )

        response_serializer = WaitingListEntrySerializer(entry)

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        entry = self.get_object()

        leave_waiting_list(
            entry=entry,
            buyer=request.user,
        )

        return Response(
            {
                "detail": "Umeondolewa kwenye waiting list.",
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="mine",
    )
    def mine(self, request):
        entries = (
            self.get_queryset()
            .filter(buyer=request.user)
            .order_by("position", "-joined_at")
        )

        serializer = WaitingListEntrySerializer(
            entries,
            many=True,
        )

        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path=r"listing/(?P<listing_id>\d+)",
    )
    def listing_entries(self, request, listing_id=None):
        if not request.user.is_staff:
            return Response(
                {
                    "detail": (
                        "Ni admin pekee anayeruhusiwa "
                        "kuona waiting list yote ya tangazo."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        entries = (
            WaitingListEntry.objects
            .select_related(
                "listing",
                "buyer",
            )
            .filter(
                listing_id=listing_id,
                status__in=[
                    WaitingListEntry.Status.WAITING,
                    WaitingListEntry.Status.NOTIFIED,
                ],
            )
            .order_by("position", "joined_at")
        )

        serializer = WaitingListEntrySerializer(
            entries,
            many=True,
        )

        return Response(serializer.data)