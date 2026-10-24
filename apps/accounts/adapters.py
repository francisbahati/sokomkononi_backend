from urllib.parse import urlencode

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from rest_framework_simplejwt.tokens import RefreshToken


FRONTEND_CALLBACK_URL = "https://www.sokomkononi.co.tz/auth/callback"


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Baada ya Apple kuthibitisha mtumiaji, tunamrudisha frontend
    na JWT (access + refresh) kwenye query string.
    Frontend (/auth/callback) inazihifadhi na kumpeleka /dashboard.
    """

    def get_connect_redirect_url(self, request, socialaccount):
        user = socialaccount.user
        refresh = RefreshToken.for_user(user)
        params = urlencode({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        })
        return f"{FRONTEND_CALLBACK_URL}?{params}"

    # Baada ya login ya kwanza (signup), allauth inaita hii
    def get_login_redirect_url(self, request):
        # Kama mtumiaji ameingia kupitia social, allauth itatumia
        # get_connect_redirect_url; hii ni fallback tu.
        return FRONTEND_CALLBACK_URL