"""
Generate WebP variants + strip EXIF from listing images.

Called from the pre_save signal in signals.py, after the watermark
signal runs. Produces 4 sizes (thumb/card/detail/large) that the
frontend uses via <picture> + srcset. Original is stored but never
served to clients.
"""
import logging
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Guard against decompression bombs (5k x 5k pixel cap)
Image.MAX_IMAGE_PIXELS = 25_000_000

# Target widths (pixels). Aspect ratio preserved.
VARIANTS = {
    "thumb":  200,
    "card":   400,
    "detail": 800,
    "large":  1200,
}

DEFAULT_QUALITY = 82


def generate_webp_variants(source_file, quality=DEFAULT_QUALITY):
    """
    Return {variant_name: ContentFile} for the source image.

    Side effects:
        - Strips all EXIF/GPS metadata (Pillow drops it when saving
          without an explicit exif= parameter).
        - Auto-rotates per the EXIF orientation tag before stripping.
        - Resizes each variant to fit its max width (never upscales).

    Raises ValueError if the file is not a valid image or is too large.
    """
    source_file.seek(0)
    try:
        img = Image.open(source_file)
        img.load()  # force decode now so errors surface immediately
    except Exception as exc:
        raise ValueError(f"Cannot open image: {exc}")

    # Rotate per EXIF orientation, then strip all metadata
    img = ImageOps.exif_transpose(img)

    # WebP supports RGBA but JPEG-derived photos are RGB.
    # Normalize to RGB for consistent output size.
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    results = {}
    for name, max_width in VARIANTS.items():
        copy = img.copy()
        if copy.width > max_width:
            new_h = int(copy.height * (max_width / copy.width))
            copy = copy.resize((max_width, new_h), Image.LANCZOS)

        buf = BytesIO()
        # No exif= param → Pillow omits all metadata from the output
        copy.save(
            buf,
            format="WEBP",
            quality=quality,
            method=6,        # slow but best compression
            optimize=True,
        )
        buf.seek(0)
        results[name] = ContentFile(buf.read())

    return results
