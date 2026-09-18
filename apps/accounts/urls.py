from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordView,
    DeleteAccountView,
    ForgotPasswordView,
    LoginView,
    LogoutView,
    MeView,
    PasswordResetView,
    ProfileView,
    RegisterView,
    VerifyOTPView,
    VerifyPasswordResetOTPView,
)


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_scope = "login"


app_name = "accounts"


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),

    path("login/", LoginView.as_view(), name="login"),
    path(
        "token/refresh/",
        ThrottledTokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),

    path("password/forgot/", ForgotPasswordView.as_view(), name="password-forgot"),
    path(
        "password/verify-otp/",
        VerifyPasswordResetOTPView.as_view(),
        name="password-verify-otp",
    ),
    path("password/reset/", PasswordResetView.as_view(), name="password-reset"),
    path(
        "password/change/",
        ChangePasswordView.as_view(),
        name="password-change",
    ),

    path("me/", MeView.as_view(), name="me"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path(
        "delete-account/",
        DeleteAccountView.as_view(),
        name="delete-account",
    ),
]