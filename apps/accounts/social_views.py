"""
Social login (Google / Apple).

POST /api/auth/social/  { provider, id_token, code? }
"""
import logging

import requests
from django.conf import settings
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import ProfileSerializer


logger = logging.getLogger(__name__)

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
APPLE_ISSUER = "https://appleid.apple.com"
APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"


class SocialLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "login"

    def post(self, request):
        provider = (request.data.get("provider") or "").strip().lower()
        id_token = (request.data.get("id_token") or "").strip()

        if provider not in ("google", "apple"):
            raise ValidationError(
                {"provider": "Provider si sahihi. Tumia google au apple."}
            )
        if not id_token:
            raise ValidationError({"id_token": "ID token inahitajika."})

        if provider == "google":
            email, name = self._verify_google(id_token)
        else:
            email, name = self._verify_apple(id_token)

        email = email.strip().lower()
        user = User.all_objects.filter(email__iexact=email).first()

        if user and user.is_deleted:
            user.restore()
        if not user:
            user = User.objects.create_user(
                email=email,
                name=name or email.split("@")[0],
                is_verified=True,
                is_active=True,
            )

        if not user.is_active:
            raise ValidationError({"detail": "Akaunti yako haipo hai."})

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "message": "Umeingia kwenye akaunti kwa mafanikio.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": ProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

    def _verify_google(self, id_token):
        try:
            r = requests.get(
                GOOGLE_TOKENINFO_URL,
                params={"id_token": id_token},
                timeout=10,
            )
        except requests.RequestException:
            logger.exception("Google tokeninfo request failed")
            raise ValidationError(
                {"id_token": "Imeshindwa kuwasiliana na Google."}
            )

        if r.status_code != 200:
            raise ValidationError({"id_token": "ID token si sahihi."})

        data = r.json()
        client_id = getattr(settings, "GOOGLE_CLIENT_ID", "") or ""
        if client_id and data.get("aud") != client_id:
            raise ValidationError(
                {"id_token": "ID token haikubaliani na client."}
            )

        email = data.get("email")
        if not email:
            raise ValidationError(
                {"id_token": "Barua pepe haipo kwenye token."}
            )

        return email, data.get("name", "")

    def _verify_apple(self, id_token):
        try:
            import jwt
            from jwt import PyJWKClient
        except ImportError:
            raise ValidationError({"id_token": "PyJWT haijasakinishwa."})

        try:
            jwks_client = PyJWKClient(APPLE_KEYS_URL)
            signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        except Exception:
            logger.exception("Apple JWKS lookup failed")
            raise ValidationError(
                {"id_token": "Imeshindwa kupata funguo za Apple."}
            )

        try:
            payload = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=APPLE_ISSUER,
                options={"verify_aud": False},
            )
        except Exception:
            raise ValidationError({"id_token": "ID token si sahihi."})

        client_id = getattr(settings, "APPLE_CLIENT_ID", "") or ""
        if client_id and payload.get("aud") != client_id:
            raise ValidationError(
                {"id_token": "ID token haikubaliani na client."}
            )

        email = payload.get("email")
        if not email:
            raise ValidationError(
                {"id_token": "Barua pepe haipo kwenye token."}
            )

        return email, ""
