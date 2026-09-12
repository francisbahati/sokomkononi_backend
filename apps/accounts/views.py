from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
)

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    LoginSerializer,
    ProfileSerializer,
    RegisterSerializer,
    VerifyOTPSerializer,
)

from .services import (
    create_pending_registration,
    send_registration_otp,
    verify_registration_otp,
)


# ============================================================
# REGISTER
# ============================================================

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                description="Usajili umeanzishwa na OTP imetumwa.",
            ),
        },
        examples=[
            OpenApiExample(
                "Register Example",
                value={
                    "name": "John Mange",
                    "email": "john@example.com",
                    "phone": "+255700000000",
                    "account_type": "INDIVIDUAL",
                    "password": "StrongPassword123",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pending = create_pending_registration(
            serializer.validated_data
        )

        verification_type = (
            "EMAIL" if pending.email else "PHONE"
        )

        send_registration_otp(
            pending,
            verification_type,
        )

        return Response(
            {
                "message": (
                    "Usajili umeanzishwa. "
                    "OTP imetumwa kwa njia uliyochagua."
                ),
                "identifier": (
                    pending.email
                    if pending.email
                    else pending.phone
                ),
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# VERIFY OTP
# ============================================================

class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=VerifyOTPSerializer,
        responses={
            200: OpenApiResponse(
                description=(
                    "OTP imethibitishwa na JWT tokens zimetolewa."
                ),
            ),
        },
        examples=[
            OpenApiExample(
                "Verify OTP Example",
                value={
                    "identifier": "john@example.com",
                    "otp_code": "123456",
                    "verification_type": "EMAIL",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = verify_registration_otp(
            identifier=serializer.validated_data["identifier"],
            otp_code=serializer.validated_data["otp_code"],
            verification_type=serializer.validated_data[
                "verification_type"
            ],
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

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                description="Login imefanikiwa.",
            ),
        },
        examples=[
            OpenApiExample(
                "Login Example",
                value={
                    "identifier": "john@example.com",
                    "password": "StrongPassword123",
                },
                request_only=True,
            ),
        ],
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
                "properties": {
                    "refresh": {
                        "type": "string",
                    }
                },
                "required": ["refresh"],
            }
        },
        responses={
            205: OpenApiResponse(
                description="Logout imefanikiwa.",
            ),
        },
    )
    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {
                    "detail": "Refresh token inahitajika."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

        except Exception:
            return Response(
                {
                    "detail": "Refresh token si sahihi au imekwisha muda."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Umetoka kwenye akaunti."
            },
            status=status.HTTP_205_RESET_CONTENT,
        )


# ============================================================
# ME
# ============================================================

class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses=ProfileSerializer,
    )
    def get(self, request):
        serializer = ProfileSerializer(request.user)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


# ============================================================
# PROFILE
# ============================================================

class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses=ProfileSerializer,
        description="Huonyesha taarifa za wasifu wa mtumiaji.",
    )
    def get(self, request):
        serializer = ProfileSerializer(request.user)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=ProfileSerializer,
        responses={
            200: ProfileSerializer,
        },
        description=(
            "Sasisha taarifa za msingi za wasifu wa mtumiaji."
        ),
        examples=[
            OpenApiExample(
                "Sasisha Wasifu",
                value={
                    "name": "John Mange",
                    "phone": "+255700000000",
                    "account_type": "BUSINESS",
                },
                request_only=True,
            ),
        ],
    )
    def patch(self, request):
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
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