# apps/finance/views_sync.py
"""
Admin endpoints za manual FimiPay sync.
"""
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.payments.services.status_sync import (
    sync_all_pending,
    sync_user_pending,
)


from apps.core.permissions import IsAdminUser  # noqa: E402
class SyncAllPendingView(APIView):
    """
    POST /api/finance/sync/all/

    Sync vyanzo vyote PENDING (admin only).
    Body: {"since_hours": 720, "dry_run": false, "no_time_filter": true}
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        since_hours = int(request.data.get("since_hours", 720))
        dry_run = bool(request.data.get("dry_run", False))
        no_time_filter = bool(request.data.get("no_time_filter", True))
        result = sync_all_pending(
            since_hours=since_hours,
            dry_run=dry_run,
            no_time_filter=no_time_filter,
        )
        return Response(result)


class SyncUserPendingView(APIView):
    """
    POST /api/finance/sync/user/<int:user_id>/

    Sync vyanzo vyote vya user mmoja (admin only).
    """
    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        from apps.accounts.models import User

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        since_hours = int(request.data.get("since_hours", 720))
        dry_run = bool(request.data.get("dry_run", False))
        no_time_filter = bool(request.data.get("no_time_filter", True))
        result = sync_user_pending(
            user,
            since_hours=since_hours,
            dry_run=dry_run,
            no_time_filter=no_time_filter,
        )
        return Response(result)


class SyncMeView(APIView):
    """
    POST /api/finance/sync/me/

    Sync vyanzo vyote vya user aliyeingia (self-service).
    Body: {"since_hours": 720, "no_time_filter": true}
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        since_hours = int(request.data.get("since_hours", 720))
        no_time_filter = bool(request.data.get("no_time_filter", True))
        result = sync_user_pending(
            request.user,
            since_hours=since_hours,
            dry_run=False,
            no_time_filter=no_time_filter,
        )
        return Response(result)