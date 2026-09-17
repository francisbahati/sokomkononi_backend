from datetime import timedelta

from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


PASSWORD_RESET_TOKEN_LIFETIME = timedelta(minutes=15)

PASSWORD_RESET_PURPOSE = "password_reset"


def create_password_reset_token(user):
    """
    Create a short-lived, single-purpose JWT used to authorize
    a password reset.

    The token:
        - expires in 15 minutes
        - carries the user id
        - carries purpose="password_reset" so it cannot be
          reused for authentication
    """
    token = AccessToken()
    token["user_id"] = user.pk
    token["purpose"] = PASSWORD_RESET_PURPOSE
    token.set_exp(lifetime=PASSWORD_RESET_TOKEN_LIFETIME)
    return str(token)


def decode_password_reset_token(token_string):
    """
    Validate and decode a password reset token.

    Returns the user id contained in the token.

    Raises ValidationError if the token is invalid, expired,
    or was not issued for password reset.
    """
    if not token_string:
        raise ValidationError(
            {"reset_token": "Reset token inahitajika."}
        )

    try:
        token = AccessToken(token_string)
    except TokenError:
        raise ValidationError(
            {
                "reset_token": (
                    "Reset token si sahihi au imekwisha muda."
                )
            }
        )

    if token.payload.get("purpose") != PASSWORD_RESET_PURPOSE:
        raise ValidationError(
            {"reset_token": "Reset token si sahihi."}
        )

    user_id = token.payload.get("user_id")

    if not user_id:
        raise ValidationError(
            {"reset_token": "Reset token haina mtumiaji."}
        )

    return user_id