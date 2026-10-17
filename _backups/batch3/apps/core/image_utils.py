"""Safe image validation — checks magic bytes, not client Content-Type."""
import io

from PIL import Image, UnidentifiedImageError


ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_AVATAR_BYTES = 3 * 1024 * 1024
MAX_LISTING_IMAGE_BYTES = 5 * 1024 * 1024
MAX_CATEGORY_IMAGE_BYTES = 5 * 1024 * 1024


def validate_image(file_obj, *, max_bytes, field="image"):
    """
    Verify the file is a real image within the allowed formats and size.
    Returns (ok, error_message).
    """
    if file_obj.size > max_bytes:
        return False, f"Faili haiwezi kuzidi {max_bytes // (1024*1024)} MB."

    try:
        pos = file_obj.tell() if hasattr(file_obj, "tell") else 0
    except Exception:
        pos = 0

    try:
        img = Image.open(file_obj)
        img.verify()
        fmt = (img.format or "").upper()
    except (UnidentifiedImageError, Exception):
        return False, "Faili si picha halali."
    finally:
        try:
            file_obj.seek(0)
        except Exception:
            pass

    if fmt not in ALLOWED_FORMATS:
        return False, "Aina ya picha hairuhusiwi. Tumia JPG, PNG au WEBP."

    return True, None
