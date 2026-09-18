"""
Cloudflare R2 storage backend for media files.

Activated in settings.py via STORAGES["default"]["BACKEND"].
"""

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class CloudflareR2MediaStorage(S3Boto3Storage):
    """
    S3-compatible storage backend for Cloudflare R2.
    """

    bucket_name = getattr(settings, "R2_BUCKET_NAME", None)
    location = getattr(settings, "R2_MEDIA_LOCATION", "media")
    custom_domain = getattr(settings, "R2_CUSTOM_DOMAIN", None)
    endpoint_url = getattr(settings, "R2_ENDPOINT_URL", None)
    access_key = getattr(settings, "R2_ACCESS_KEY_ID", None)
    secret_key = getattr(settings, "R2_SECRET_ACCESS_KEY", None)
    region_name = "auto"
    signature_version = "s3v4"
    querystring_auth = False
    file_overwrite = False
    default_acl = None  # R2 ignores ACLs; use signed URLs or public bucket