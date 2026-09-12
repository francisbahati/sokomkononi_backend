from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    LogoutView,
    MeView,
    ProfileView,
    RegisterView,
    VerifyOTPView,
)


app_name = "accounts"


urlpatterns = [
    # --------------------------------------------------------
    # AUTHENTICATION
    # --------------------------------------------------------

    path(
        "register/",
        RegisterView.as_view(),
        name="register",
    ),

    path(
        "verify-otp/",
        VerifyOTPView.as_view(),
        name="verify-otp",
    ),

    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),

    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),

    path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),

    # --------------------------------------------------------
    # USER
    # --------------------------------------------------------

    path(
        "me/",
        MeView.as_view(),
        name="me",
    ),

    path(
        "profile/",
        ProfileView.as_view(),
        name="profile",
    ),
]