"""2FA + Sessions + Data Export views.

Mabadiliko:
  - ✅ DataExportView sasa inarudisha { url, filename, expires_at, size_bytes }
    badala ya HttpResponse moja kwa moja. Faili linahifadhiwa kwenye
    `default_storage` (local au R2) na linafutwa baada ya siku 7 kupitia
    Celery task `accounts.cleanup_old_data_exports`.
"""
import json
import secrets

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
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


# ============================================================
# DATA EXPORT — sasa inarudisha { url } kwa download halisi
# ============================================================
class DataExportView(APIView):
    """
    POST /api/auth/me/data-export/

    Inatengeneza faili la JSON na kulihifadhi kwenye `default_storage`
    (local au R2). Inarudisha URL ya kupakua + metadata.

    Faili linafutwa baada ya `DATA_EXPORT_RETENTION_DAYS` (default 7)
    kupitia Celery task `accounts.cleanup_old_data_exports`.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.listings.models import Listing
        from apps.deals.models import DealRoom
        from apps.transactions.models import Transaction
        from apps.bundles.models import BundlePurchase
        from apps.saved.models import SavedListing
        from apps.searches.models import SavedSearch

        user = request.user

        # ✅ Tengeneza payload ya data zote za mtumiaji
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
            "transactions_as_buyer": list(
                Transaction.objects.filter(buyer=user).values(
                    "id", "status", "agreed_price", "created_at",
                )
            ),
            "transactions_as_seller": list(
                Transaction.objects.filter(seller=user).values(
                    "id", "status", "agreed_price", "created_at",
                )
            ),
            "bundle_purchases": list(
                BundlePurchase.objects.filter(user=user).values(
                    "id", "amount", "status", "created_at",
                )
            ),
            "saved_listings": list(
                SavedListing.objects.filter(user=user).values(
                    "listing_id", "saved_at",
                )
            ),
            "saved_searches": list(
                SavedSearch.objects.filter(user=user).values(
                    "id", "name", "query", "category_slug",
                    "region", "min_price", "max_price",
                    "verified_only", "created_at",
                )
            ),
            "exported_at": timezone.now().isoformat(),
        }

        # ✅ Serialize JSON
        blob = json.dumps(payload, default=str, indent=2).encode("utf-8")

        # ✅ Jina la faili: data-exports/user_<id>/sokomkononi-data-<ts>-<rand>.json
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = secrets.token_hex(4)
        filename = (
            f"data-exports/user_{user.pk}/"
            f"sokomkononi-data-{timestamp}-{random_suffix}.json"
        )

        # ✅ Hifadhi kwenye storage
        saved_path = default_storage.save(filename, ContentFile(blob))

        # ✅ Tengeneza URL
        try:
            url = default_storage.url(saved_path)
            # Kama ni URL ya jamaa (relative), ifanye absolute
            if url and not url.startswith(("http://", "https://")):
                url = request.build_absolute_uri(url)
        except Exception:
            url = f"{settings.MEDIA_URL}{saved_path}"

        retention_days = getattr(settings, "DATA_EXPORT_RETENTION_DAYS", 7)
        expires_at = timezone.now() + timezone.timedelta(days=retention_days)

        return Response({
            "url": url,
            "filename": filename.split("/")[-1],
            "expires_at": expires_at.isoformat(),
            "size_bytes": len(blob),
            "retention_days": retention_days,
        })