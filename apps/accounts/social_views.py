# apps/accounts/social_views.py
import logging

import jwt as pyjwt
import requests as http_requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

logger = logging.getLogger(__name__)
User = get_user_model()

APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"


def _issue_jwt(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "account_type": user.account_type,
            "is_verified": getattr(user, "is_verified", False),
            "role": "Admin" if user.is_staff or user.is_superuser else (
                "Seller" if user.account_type == "BUSINESS" else "Buyer"
            ),
        },
    }


def _verify_google_id_token(id_token):
    try:
        claims = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception as exc:
        raise ValidationError(f"Uthibitisho wa Google umeshindwa: {exc}")
    return claims


def _verify_apple_id_token(id_token):
    """Thibitisha Apple id_token kwa public keys za Apple."""
    try:
        resp = http_requests.get(APPLE_KEYS_URL, timeout=10)
        resp.raise_for_status()
        jwks = resp.json()
    except Exception as exc:
        raise ValidationError(f"Imeshindwa kupata Apple keys: {exc}")

    try:
        unverified_header = pyjwt.get_unverified_header(id_token)
    except Exception as exc:
        raise ValidationError(f"id_token si sahihi: {exc}")

    kid = unverified_header.get("kid")
    key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
    if not key:
        raise ValidationError("Apple public key haipatikani kwa kid hii.")

    try:
        claims = pyjwt.decode(
            id_token,
            key=pyjwt.algorithms.RSAAlgorithm.from_jwk(key),
            algorithms=["RS256"],
            audience=settings.APPLE_SERVICES_ID,
            issuer=APPLE_ISSUER,
        )
    except Exception as exc:
        raise ValidationError(f"Uthibitisho wa Apple umeshindwa: {exc}")

    return claims


@method_decorator(csrf_exempt, name="dispatch")
class SocialLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        provider = (request.data.get("provider") or "").lower()
        id_token_raw = request.data.get("id_token")
        social_user = request.data.get("user") or {}

        if not provider or not id_token_raw:
            return Response(
                {"detail": "provider na id_token zinahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if provider == "google":
                claims = _verify_google_id_token(id_token_raw)
                email = claims.get("email")
                sub = claims.get("sub")
                name = claims.get("name") or (email.split("@")[0] if email else "mteja")
                username_key = f"google_{sub}"
            elif provider == "apple":
                claims = _verify_apple_id_token(id_token_raw)
                email = claims.get("email")
                sub = claims.get("sub")
                name = ""
                if social_user and social_user.get("name"):
                    n = social_user["name"]
                    name = f"{n.get('firstName', '')} {n.get('lastName', '')}".strip()
                if not name:
                    name = claims.get("name") or (email.split("@")[0] if email else "mteja")
                username_key = f"apple_{sub}"
            else:
                return Response(
                    {"detail": f"Provider '{provider}' haitumiki."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValidationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not email:
            return Response(
                {"detail": "Barua pepe haipatikani kwenye token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            user = User.objects.create_user(
                email=email,
                name=name,
                password=None,
                is_active=True,
            )
            if hasattr(user, "email_verified"):
                user.email_verified = True
                user.save(update_fields=["email_verified"])

            if hasattr(user, "username"):
                base_username = username_key
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    counter += 1
                    username = f"{base_username}_{counter}"
                user.username = username
                user.save(update_fields=["username"])
        else:
            if not user.name and name:
                user.name = name
                user.save(update_fields=["name"])

        return Response(_issue_jwt(user), status=status.HTTP_200_OK)