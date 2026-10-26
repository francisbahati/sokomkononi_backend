"""2FA + Sessions + Data Export views."""
import json

from django.http import HttpResponse
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, UserSession
from .serializers import ProfileSerializer
from .totp import (
    build_provisioning_uri,
    clear_failures,
    generate_recovery_codes,
    get_or_create_totp,
    is_locked,
    register_failure,
    verify_recovery_code,
    verify_totp,
)
from .tokens import decode_2fa_challenge_token

LOCKED_MSG = "Majaribio mengi yameshindwa. Subiri dakika 10 kisha ujaribu tena."
ADMIN_MSG = "Akaunti za admin hazitumii 2FA."


def _is_admin(user):
    return bool(user.is_staff or user.is_superuser)


def _qr_data_uri(text):
    """QR kama data URI (SVG) kwa kutumia `segno`. None ikikosekana."""
    try:
        import segno
        return segno.make(text, error="m").svg_data_uri(scale=6, border=2)
    except Exception:
        return None


def _first_error(detail):
    """Toa ujumbe mmoja kutoka kwa ValidationError (dict/list/str)."""
    if isinstance(detail, dict):
        detail = next(iter(detail.values()), "")
    if isinstance(detail, (list, tuple)):
        detail = detail[0] if detail else ""
    return str(detail)


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
        if _is_admin(request.user):
            return Response({"detail": ADMIN_MSG}, status=status.HTTP_403_FORBIDDEN)
        existing = getattr(request.user, "totp", None)
        if existing and existing.enabled:
            # Usionyeshe secret tena baada ya 2FA kuwashwa
            return Response(
                {"detail": "2FA tayari imewashwa."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        t = get_or_create_totp(request.user)
        uri = build_provisioning_uri(request.user)
        return Response({
            "provisioning_uri": uri,
            "qr_url": _qr_data_uri(uri),
            "secret": t.secret,
        })


class TwoFactorVerifyView(APIView):
    """Inathibitisha code ya kwanza na kuwasha 2FA."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if _is_admin(user):
            return Response({"detail": ADMIN_MSG}, status=status.HTTP_403_FORBIDDEN)
        if is_locked(user):
            return Response({"detail": LOCKED_MSG}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        t = get_or_create_totp(user)
        if t.enabled:
            return Response(
                {"detail": "2FA tayari imewashwa."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = (request.data.get("code") or "").strip()
        # require_enabled=False: 2FA bado haijawashwa, tunathibitisha setup
        if not verify_totp(user, code, require_enabled=False):
            register_failure(user)
            return Response(
                {"detail": "Nambari si sahihi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        clear_failures(user)
        t.enabled = True
        t.save(update_fields=["enabled"])
        codes = generate_recovery_codes(user)
        return Response({
            "enabled": True,
            "recovery_codes": codes,
        })


class TwoFactorDisableView(APIView):
    """Kuzima 2FA kunahitaji nenosiri + code (TOTP au recovery)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        t = getattr(user, "totp", None)
        if not (t and t.enabled):
            return Response({"enabled": False})

        if is_locked(user):
            return Response({"detail": LOCKED_MSG}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        password = request.data.get("password") or ""
        code = (request.data.get("code") or "").strip()

        if not user.check_password(password):
            register_failure(user)
            return Response(
                {"detail": "Nenosiri si sahihi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (verify_totp(user, code) or verify_recovery_code(user, code)):
            register_failure(user)
            return Response(
                {"detail": "Nambari si sahihi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        clear_failures(user)
        t.enabled = False
        t.secret = ""            # secret mpya itatengenezwa ukiwasha tena
        t.recovery_codes = []
        t.save(update_fields=["enabled", "secret", "recovery_codes"])
        return Response({"enabled": False})


class TwoFactorRecoveryCodesView(APIView):
    """Tengeneza recovery codes mpya (za zamani zinafutwa). Inahitaji code."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        t = getattr(user, "totp", None)
        if not (t and t.enabled):
            return Response(
                {"detail": "2FA haijawashwa."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if is_locked(user):
            return Response({"detail": LOCKED_MSG}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        code = (request.data.get("code") or "").strip()
        if not verify_totp(user, code):
            register_failure(user)
            return Response(
                {"detail": "Nambari si sahihi."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        clear_failures(user)
        return Response({"recovery_codes": generate_recovery_codes(user)})


class TwoFactorChallengeView(APIView):
    """POST /api/auth/2fa/login/ {code_token, code}"""
    permission_classes = [permissions.AllowAny]
    throttle_scope = "login"

    def post(self, request):
        code_token = request.data.get("code_token") or ""
        code = (request.data.get("code") or "").strip()

        try:
            user_id = decode_2fa_challenge_token(code_token)
        except ValidationError as exc:
            return Response(
                {"detail": _first_error(exc.detail)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(pk=user_id, is_active=True).first()
        if not user or _is_admin(user):
            return Response(
                {"detail": "Mtumiaji haipatikani."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if is_locked(user):
            return Response({"detail": LOCKED_MSG}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        if not (verify_totp(user, code) or verify_recovery_code(user, code)):
            register_failure(user)
            return Response(
                {"detail": "Nambari si sahihi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        clear_failures(user)
        refresh = RefreshToken.for_user(user)
        return Response({
            "message": "Umeingia kwenye akaunti kwa mafanikio.",
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