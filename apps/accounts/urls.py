from django.urls import path

from .views import PublicStatsView 

from rest_framework_simplejwt.views import TokenRefreshView

from .social_views import SocialLoginView
from .views_2fa import (
    DataExportView,
    RevokeOtherSessionsView,
    SessionsView,
    TwoFactorChallengeView,
    TwoFactorDisableView,
    TwoFactorRecoveryCodesView,
    TwoFactorSetupView,
    TwoFactorStatusView,
    TwoFactorVerifyView,
)
from .views import (
    AvatarUploadView,
    ChangePasswordView,
    DeleteAccountView,
    ForgotPasswordView,
    LoginView,
    LogoutView,
    MeActivitiesView,
    MeNotificationPreferencesView,
    MePreferencesView,
    MeView,
    PasswordResetView,
    ProfileView,
    RegisterView,
    VerifyOTPView,
    VerifyPasswordResetOTPView,
    ResendOTPView,
)


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_scope = "refresh"


app_name = "accounts"


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),

    path("login/", LoginView.as_view(), name="login"),
    path("stats/public/", PublicStatsView.as_view(), name="public-stats"),
    path("social/", SocialLoginView.as_view(), name="social-login"),
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
    path(
        "me/preferences/",
        MePreferencesView.as_view(),
        name="me-preferences",
    ),
    path(
        "me/notification-preferences/",
        MeNotificationPreferencesView.as_view(),
        name="me-notification-preferences",
    ),
    path(
        "me/activities/",
        MeActivitiesView.as_view(),
        name="me-activities",
    ),

    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/avatar/", AvatarUploadView.as_view(), name="profile-avatar"),
    path(
        "delete-account/",
        DeleteAccountView.as_view(),
        name="delete-account",
    ),

    # ---------------- 2FA ----------------
    path("2fa/status/", TwoFactorStatusView.as_view(), name="2fa-status"),
    path("2fa/setup/", TwoFactorSetupView.as_view(), name="2fa-setup"),
    path("2fa/verify/", TwoFactorVerifyView.as_view(), name="2fa-verify"),
    path("2fa/disable/", TwoFactorDisableView.as_view(), name="2fa-disable"),
    path(
        "2fa/recovery-codes/",
        TwoFactorRecoveryCodesView.as_view(),
        name="2fa-recovery-codes",
    ),
    path("2fa/login/", TwoFactorChallengeView.as_view(), name="2fa-login"),

    # ------- Sessions + data export -------
    path("sessions/", SessionsView.as_view(), name="sessions"),
    path("sessions/<int:pk>/", SessionsView.as_view(), name="session-detail"),
    path(
        "sessions/revoke-others/",
        RevokeOtherSessionsView.as_view(),
        name="sessions-revoke-others",
    ),
    path("me/data-export/", DataExportView.as_view(), name="data-export"),
]