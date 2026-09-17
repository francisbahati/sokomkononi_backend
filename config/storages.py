from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class CloudflareR2MediaStorage(S3Boto3Storage):
    """
    Custom storage backend for Cloudflare R2.

    Uses the S3-compatible API. All media files are stored in a
    single bucket, prefixed with a configurable location path.
    """
    bucket_name = getattr(settings, "R2_BUCKET_NAME", None)
    location = getattr(settings, "R2_MEDIA_LOCATION", "media")
    custom_domain = getattr(settings, "R2_CUSTOM_DOMAIN", None)
    endpoint_url = getattr(settings, "R2_ENDPOINT_URL", None)
    access_key = getattr(settings, "R2_ACCESS_KEY_ID", None)
    secret_key = getattr(settings, "R2_SECRET_ACCESS_KEY", None)
    region_name = "auto"
    signature_version = "s3v4"
    querystring_auth = False  # Set to True if you want signed URLs
    file_overwrite = False
    default_acl = "public-read"  # R2 ignores ACLs, but boto3 requires a value