"""2FA + Sessions + Data Export views."""
import json

from django.http import HttpResponse
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserSession
from .serializers import ProfileSerializer
from .totp import (
    build_provisioning_uri,
    generate_recovery_codes,
    get_or_create_totp,
    verify_recovery_code,
    verify_totp,
)
from .tokens import decode_2fa_challenge_token


class TwoFactorStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        t = getattr(request.user, "totp", None)
        return Response({
            "enabled": bool(t and t.enabled),
            "recovery_codes_remaining": len(t.recovery_codes) if t else 0,
        })


class TwoFactorSetupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        t = get_or_create_totp(request.user)
        return Response({
            "provisioning_uri": build_provisioning_uri(request.user),
            "secret": t.secret,
        })


class TwoFactorVerifyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = (request.data.get("code") or "").strip()
        if not verify_totp(request.user, code):
            return Response(
                {"detail": "Nambari si sahihi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        t = get_or_create_totp(request.user)
        t.enabled = True
        t.save(update_fields=["enabled"])
        codes = generate_recovery_codes(request.user)
        return Response({
            "enabled": True,
            "recovery_codes": codes,
        })


class TwoFactorDisableView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        t = getattr(request.user, "totp", None)
        if t:
            t.enabled = False
            t.save(update_fields=["enabled"])
        return Response({"enabled": False})


class TwoFactorChallengeView(APIView):
    """POST /api/auth/2fa/login/ {code_token, code}"""
    permission_classes = [permissions.AllowAny]
    throttle_scope = "login"

    def post(self, request):
        code_token = request.data.get("code_token") or ""
        code = (request.data.get("code") or "").strip()

        try:
            user_id = decode_2fa_challenge_token(code_token)
        except Exception as exc:
            return Response(
                {"detail": getattr(exc, "detail", str(exc))},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(pk=user_id).first()
        if not user:
            return Response(
                {"detail": "Mtumiaji haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not (verify_totp(user, code) or verify_recovery_code(user, code)):
            return Response(
                {"detail": "Nambari si sahihi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": ProfileSerializer(user).data,
        })


class SessionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        rows = UserSession.objects.filter(user=request.user)
        return Response([
            {
                "id": s.pk,
                "device_name": s.device_name,
                "ip_address": s.ip_address,
                "last_seen": s.last_seen,
                "created_at": s.created_at,
            }
            for s in rows
        ])

    def delete(self, request, pk=None):
        UserSession.objects.filter(user=request.user, pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RevokeOtherSessionsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken, OutstandingToken,
        )
        current_jti = request.data.get("current_jti") or ""
        others = UserSession.objects.filter(user=request.user).exclude(
            refresh_jti=current_jti,
        )
        jtis = list(others.values_list("refresh_jti", flat=True))
        for token in OutstandingToken.objects.filter(jti__in=jtis):
            BlacklistedToken.objects.get_or_create(token=token)
        others.delete()
        return Response({"revoked": len(jtis)})


class DataExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.listings.models import Listing
        from apps.deals.models import DealRoom
        from apps.transactions.models import Transaction

        user = request.user
        payload = {
            "user": ProfileSerializer(user).data,
            "listings": list(Listing.objects.filter(seller=user).values(
                "id", "title", "price", "status", "created_at",
            )),
            "deals_as_buyer": list(DealRoom.objects.filter(buyer=user).values(
                "id", "listing_id", "status", "created_at",
            )),
            "deals_as_seller": list(DealRoom.objects.filter(seller=user).values(
                "id", "listing_id", "status", "created_at",
            )),
            "transactions": list(
                Transaction.objects.filter(buyer=user).values(
                    "id", "status", "agreed_price",
                )
            ) + list(
                Transaction.objects.filter(seller=user).values(
                    "id", "status", "agreed_price",
                )
            ),
            "exported_at": timezone.now().isoformat(),
        }
        response = HttpResponse(
            json.dumps(payload, default=str, indent=2),
            content_type="application/json",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="sokomkononi-data-{user.pk}.json"'
        )
        return response
