"""
Short-lived, single-purpose JWT tokens for password reset.

The token type is deliberately DIFFERENT from an access token so that
FlexibleJWTAuthentication / JWTAuthentication reject it when presented
as a bearer token.
"""
from datetime import timedelta

from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import Token


PASSWORD_RESET_TOKEN_LIFETIME = timedelta(minutes=15)
PASSWORD_RESET_PURPOSE = "password_reset"
PASSWORD_RESET_TOKEN_TYPE = "password_reset"


class PasswordResetToken(Token):
    """A JWT that can ONLY be used to authorize a password reset."""
    token_type = PASSWORD_RESET_TOKEN_TYPE
    lifetime = PASSWORD_RESET_TOKEN_LIFETIME


def create_password_reset_token(user):
    token = PasswordResetToken()
    token["user_id"] = user.pk
    token["purpose"] = PASSWORD_RESET_PURPOSE
    return str(token)


def decode_password_reset_token(token_string):
    if not token_string:
        raise ValidationError({"reset_token": "Reset token inahitajika."})
    try:
        token = PasswordResetToken(token_string)
    except TokenError:
        raise ValidationError({
            "reset_token": "Reset token si sahihi au imekwisha muda."
        })
    if token.payload.get("purpose") != PASSWORD_RESET_PURPOSE:
        raise ValidationError({"reset_token": "Reset token si sahihi."})
    user_id = token.payload.get("user_id")
    if not user_id:
        raise ValidationError({"reset_token": "Reset token haina mtumiaji."})
    return user_id


# ============================================================
# 2FA CHALLENGE TOKEN
# ============================================================
TWO_FACTOR_PURPOSE = "2fa_challenge"


class TwoFactorChallengeToken(Token):
    token_type = "2fa_challenge"
    lifetime = timedelta(minutes=5)


def create_2fa_challenge_token(user):
    token = TwoFactorChallengeToken()
    token["user_id"] = user.pk
    token["purpose"] = TWO_FACTOR_PURPOSE
    return str(token)


def decode_2fa_challenge_token(token_string):
    if not token_string:
        raise ValidationError({"code_token": "code_token inahitajika."})
    try:
        token = TwoFactorChallengeToken(token_string)
    except TokenError:
        raise ValidationError({
            "code_token": "Token si sahihi au imeisha muda."
        })
    if token.payload.get("purpose") != TWO_FACTOR_PURPOSE:
        raise ValidationError({"code_token": "Token si sahihi."})
    user_id = token.payload.get("user_id")
    if not user_id:
        raise ValidationError({"code_token": "Token haina mtumiaji."})
    return user_id
