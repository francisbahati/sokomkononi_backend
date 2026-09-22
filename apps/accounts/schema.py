"""
OpenAPI schema extension for FlexibleJWTAuthentication.

Silences the recurring drf-spectacular warning:

    could not resolve authenticator <FlexibleJWTAuthentication>

and documents the Bearer token scheme in /api/docs/.
"""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class FlexibleJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.FlexibleJWTAuthentication"
    name = "FlexibleJWT"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "JWT access token. Provide as 'Authorization: Bearer <token>'. "
                "Alternate sources accepted: cookie 'access_token', "
                "query '?token=<jwt>', or header 'X-Access-Token'."
            ),
        }
