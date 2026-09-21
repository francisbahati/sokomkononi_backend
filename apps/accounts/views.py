# ============================================================
# apps/accounts/views.py
# ============================================================

import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema

from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    PasswordResetSerializer,
    ProfileSerializer,
    RegisterSerializer,
    VerifyOTPSerializer,
    VerifyPasswordResetOTPSerializer,
)
from .services import (
    create_pending_registration,
    delete_user_account,
    reset_user_password,
    resolve_identifier,
    send_password_reset_otp,
    send_registration_otp,
    verify_password_reset_otp,
    verify_registration_otp,
)
from .tokens import (
    create_password_reset_token,
    decode_password_reset_token,
)


logger = logging.getLogger(__name__)


# ============================================================
# REGISTER
# ============================================================

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "register"

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                description="Usajili umeanzishwa na OTP imetumwa.",
            ),
        },
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pending = create_pending_registration(serializer.validated_data)
        verification_type = "EMAIL" if pending.email else "PHONE"

        otp_sent = True
        try:
            send_registration_otp(pending, verification_type)
        except Exception:
            otp_sent = False
            logger.exception(
                "Failed to send registration OTP for %s", pending.pk,
            )

        return Response(
            {
                "message": (
                    "Usajili umeanzishwa. OTP imetumwa."
                    if otp_sent
                    else (
                        "Usajili umeanzishwa, lakini OTP haikutumwa. "
                        "Tafadhali omba kutuma tena."
                    )
                ),
                "otp_sent": otp_sent,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# VERIFY OTP (registration)
# ============================================================

class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "otp_verify"

    @extend_schema(
        request=VerifyOTPSerializer,
        responses={
            200: OpenApiResponse(
                description="OTP imethibitishwa na JWT zimetolewa.",
            ),
        },
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = verify_registration_otp(
            identifier=serializer.validated_data["identifier"],
            otp_code=serializer.validated_data["otp_code"],
            verification_type=serializer.validated_data["verification_type"],
        )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Akaunti imethibitishwa kikamilifu.",
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": ProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# LOGIN
# ============================================================

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "login"

    @extend_schema(
        request=LoginSerializer,
        responses={200: OpenApiResponse(description="Login imefanikiwa.")},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
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


# ============================================================
# LOGOUT
# ============================================================

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {"refresh": {"type": "string"}},
                "required": ["refresh"],
            },
        },
        responses={205: OpenApiResponse(description="Logout imefanikiwa.")},
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token inahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            return Response(
                {"detail": "Refresh token si sahihi au imekwisha muda."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Umetoka kwenye akaunti."},
            status=status.HTTP_205_RESET_CONTENT,
        )


# ============================================================
# ME
# ============================================================

class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=ProfileSerializer)
    def get(self, request):
        return Response(
            ProfileSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )


# ============================================================
# PROFILE
# ============================================================

class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses=ProfileSerializer)
    def get(self, request):
        return Response(
            ProfileSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
    )
    def patch(self, request):
        serializer = ProfileSerializer(
            request.user, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Wasifu umefanikiwa kusasishwa.",
                "profile": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# CHANGE PASSWORD
# ============================================================

class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: OpenApiResponse(description="Nenosiri limebadilishwa.")},
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password", "updated_at"])

        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken,
                OutstandingToken,
            )
            outstanding = OutstandingToken.objects.filter(user=request.user)
            BlacklistedToken.objects.bulk_create(
                [BlacklistedToken(token=t) for t in outstanding],
                ignore_conflicts=True,
            )
        except ImportError:
            pass

        return Response(
            {"message": "Nenosiri limebadilishwa kwa mafanikio."},
            status=status.HTTP_200_OK,
        )


# ============================================================
# DELETE ACCOUNT
# ============================================================

class DeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
            },
        },
        responses={
            200: OpenApiResponse(
                description="Akaunti imewekwa kwenye kikapu kwa siku 90.",
            ),
        },
    )
    def post(self, request):
        delete_user_account(
            user=request.user,
            actor=request.user,
            reason=request.data.get("reason", ""),
        )

        return Response(
            {
                "detail": (
                    "Akaunti yako imewekwa kwenye kikapu. "
                    "Itaondolewa kabisa baada ya siku 90."
                ),
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# FORGOT PASSWORD — step 1
# ============================================================

class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(
        request=ForgotPasswordSerializer,
        responses={
            200: OpenApiResponse(
                description="OTP imetumwa kama akaunti ipo.",
            ),
        },
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identifier = serializer.validated_data["identifier"]

        generic_response = {
            "message": (
                "Kama akaunti ipo, OTP imetumwa. "
                "Angalia barua pepe au ujumbe wa simu."
            ),
        }

        try:
            normalized, base_type = resolve_identifier(identifier)
        except ValidationError:
            return Response(generic_response, status=status.HTTP_200_OK)

        if base_type == "EMAIL":
            user = User.objects.filter(email__iexact=normalized).first()
        else:
            user = User.objects.filter(phone=normalized).first()

        if not user:
            return Response(generic_response, status=status.HTTP_200_OK)

        try:
            send_password_reset_otp(user, base_type)
        except Exception:
            logger.exception(
                "Failed to send password reset OTP for user %s", user.pk,
            )

        return Response(generic_response, status=status.HTTP_200_OK)


# ============================================================
# FORGOT PASSWORD — step 2
# ============================================================

class VerifyPasswordResetOTPView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(
        request=VerifyPasswordResetOTPSerializer,
        responses={
            200: OpenApiResponse(
                description="OTP imethibitishwa. Tumia reset_token.",
            ),
        },
    )
    def post(self, request):
        serializer = VerifyPasswordResetOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = verify_password_reset_otp(
            identifier=serializer.validated_data["identifier"],
            otp_code=serializer.validated_data["otp_code"],
            verification_type=serializer.validated_data["verification_type"],
        )

        reset_token = create_password_reset_token(user)

        return Response(
            {
                "message": (
                    "OTP imethibitishwa. Tumia reset_token "
                    "kubadilisha nenosiri lako."
                ),
                "reset_token": reset_token,
                "expires_in_minutes": 15,
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# FORGOT PASSWORD — step 3
# ============================================================

class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(
        request=PasswordResetSerializer,
        responses={200: OpenApiResponse(description="Nenosiri limebadilishwa.")},
    )
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = decode_password_reset_token(
            serializer.validated_data["reset_token"]
        )

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise ValidationError({"reset_token": "Mtumiaji haipatikani."})

        reset_user_password(user, serializer.validated_data["new_password"])

        return Response(
            {
                "message": (
                    "Nenosiri limebadilishwa kwa mafanikio. "
                    "Tafadhali ingia upya kwa nenosiri jipya."
                ),
            },
            status=status.HTTP_200_OK,
        )

# ============================================================
# AVATAR UPLOAD / REMOVE
# ============================================================

class AvatarUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        f = request.FILES.get("avatar")
        if not f:
            return Response(
                {"detail": "Picha inahitajika."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        allowed = ["image/jpeg", "image/png", "image/webp"]
        if f.content_type not in allowed:
            return Response(
                {"detail": "Aina ya picha hairuhusiwi. Tumia JPG, PNG au WEBP."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if f.size > 3 * 1024 * 1024:
            return Response(
                {"detail": "Picha haiwezi kuzidi 3 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.avatar = f
        request.user.save(update_fields=["avatar", "updated_at"])

        url = None
        if request.user.avatar:
            url = request.build_absolute_uri(request.user.avatar.url)

        return Response(
            {"detail": "Picha imepakiwa.", "avatar": url},
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        if request.user.avatar:
            request.user.avatar.delete(save=False)
            request.user.avatar = None
            request.user.save(update_fields=["avatar", "updated_at"])
        return Response(
            {"detail": "Picha imeondolewa."},
            status=status.HTTP_200_OK,
        )
