# apps/accounts/social_views.py
import logging

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


@method_decorator(csrf_exempt, name="dispatch")
class SocialLoginView(APIView):
    """
    Google Sign-In (popup flow). Apple inatumia django-allauth
    (/accounts/apple/login/), sio view hii.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        provider = (request.data.get("provider") or "").lower()
        id_token_raw = request.data.get("id_token")

        if not provider or not id_token_raw:
            return Response(
                {"detail": "provider na id_token zinahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if provider != "google":
            return Response(
                {
                    "detail": (
                        f"Provider '{provider}' haitumiki hapa. "
                        "Tumia /accounts/apple/login/ kwa Apple."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            claims = _verify_google_id_token(id_token_raw)
            email = claims.get("email")
            sub = claims.get("sub")
            name = claims.get("name") or (email.split("@")[0] if email else "mteja")
            username_key = f"google_{sub}"
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
                # email_verified=True, # <--- Imeondolewa kwa usalama wa model yako
            )
            # Weka email_verified tu kama model ina sehemu hiyo
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