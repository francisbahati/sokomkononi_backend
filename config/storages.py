"""
Cloudflare R2 storage backend for media files.

Activated in settings.py via STORAGES["default"]["BACKEND"].
"""
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


def _normalize_domain(domain):
    """Fix common typos: https// → https://, strip trailing slash."""
    if not domain:
        return None
    domain = domain.strip()
    domain = domain.replace("https//", "https://").replace("http//", "http://")
    return domain.rstrip("/") or None


class CloudflareR2MediaStorage(S3Boto3Storage):
    """S3-compatible storage backend for Cloudflare R2."""

    bucket_name = getattr(settings, "R2_BUCKET_NAME", None)
    location = getattr(settings, "R2_MEDIA_LOCATION", "media")
    custom_domain = _normalize_domain(getattr(settings, "R2_CUSTOM_DOMAIN", None))
    endpoint_url = getattr(settings, "R2_ENDPOINT_URL", None)
    access_key = getattr(settings, "R2_ACCESS_KEY_ID", None)
    secret_key = getattr(settings, "R2_SECRET_ACCESS_KEY", None)
    region_name = "auto"
    signature_version = "s3v4"
    querystring_auth = False
    file_overwrite = False
    default_acl = None
    # Emit a 1-year immutable Cache-Control header on every upload.
    # Safe because filenames include a UUID — replacing an image
    # produces a new URL, so old cached entries never go stale.
    object_parameters = {
        "CacheControl": "public, max-age=31536000, immutable",
    }
