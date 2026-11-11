import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageOps


WATERMARK_TEXT = "SokoMkononi.co.tz"
WATERMARK_TEXT_COLOR = (255, 255, 255, 230)       # nyeupe 90%
WATERMARK_SHADOW_COLOR = (0, 0, 0, 180)           # nyeusi 70%
WATERMARK_FONT_SIZE = 28
WATERMARK_PADDING = 20

# ── Badge ya background kwa watermark ──────────────────────
WATERMARK_BADGE_BG = (1, 25, 87, 200)             # navy 78%
WATERMARK_BADGE_RADIUS = 8
WATERMARK_BADGE_PAD_X = 14
WATERMARK_BADGE_PAD_Y = 8


def get_font(size=WATERMARK_FONT_SIZE):
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _rounded_rectangle(draw, xy, radius, fill):
    """Chora rounded rectangle (badge) kwa watermark."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(
        (x0, y0, x1, y1),
        radius=radius,
        fill=fill,
    )


def add_watermark(image_file, text=None, position="bottom-left"):
    """
    Ongeza watermark kwenye picha bila kuondoa ubora na bila kuficha.

    position: "bottom-left" (default) | "bottom-right" | "top-left" | "top-right" | "center"
    """
    if text is None:
        text = WATERMARK_TEXT

    # Seek(0) kabla ya Image.open() — muhimu kwa InMemoryUploadedFile
    try:
        image_file.seek(0)
    except Exception:
        pass

    img = Image.open(image_file)
    original_mode = img.mode
    original_format = img.format or "JPEG"

    # Picha za simu zina EXIF orientation; tukihifadhi bila EXIF zinazunguka vibaya.
    # Zungusha pikseli sasa ili watermark iwe mahali sahihi na picha ibaki wima.
    img = ImageOps.exif_transpose(img)

    # Convert to RGBA for compositing
    if img.mode not in ("RGBA", "RGB"):
        img = img.convert("RGBA")
    elif img.mode == "RGB":
        img = img.convert("RGBA")

    width, height = img.size

    # Ukubwa wa watermark unalingana na upana wa picha (msingi: 1200px).
    # Bila hii, picha ya 4000px ingepata watermark ndogo isiyosomeka
    # baada ya kupunguzwa kuwa thumb/card/detail.
    scale = max(width / 1200.0, 0.5)
    font_size = int(WATERMARK_FONT_SIZE * scale)
    padding = int(WATERMARK_PADDING * scale)
    pad_x = int(WATERMARK_BADGE_PAD_X * scale)
    pad_y = int(WATERMARK_BADGE_PAD_Y * scale)
    radius = int(WATERMARK_BADGE_RADIUS * scale)

    watermark_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_layer)

    font = get_font(font_size)

    # ── Pima ukubwa wa maandishi ───────────────────────────
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # ── Ukubwa wa badge ────────────────────────────────────
    badge_width = text_width + (pad_x * 2)
    badge_height = text_height + (pad_y * 2)

    # ── Chagua mahali ──────────────────────────────────────
    if position == "bottom-right":
        badge_x = width - badge_width - padding
        badge_y = height - badge_height - padding
    elif position == "top-left":
        badge_x = padding
        badge_y = padding
    elif position == "top-right":
        badge_x = width - badge_width - padding
        badge_y = padding
    elif position == "center":
        badge_x = (width - badge_width) // 2
        badge_y = (height - badge_height) // 2
    else:  # "bottom-left" (default)
        badge_x = padding
        badge_y = height - badge_height - padding

    # ── Chora badge ────────────────────────────────────────
    _rounded_rectangle(
        draw,
        (
            badge_x,
            badge_y,
            badge_x + badge_width,
            badge_y + badge_height,
        ),
        radius=radius,
        fill=WATERMARK_BADGE_BG,
    )

    # ── Chora maandishi ────────────────────────────────────
    text_x = badge_x + pad_x
    text_y = badge_y + pad_y

    # Shadow
    shadow_offset = max(1, int(scale))
    draw.text(
        (text_x + shadow_offset, text_y + shadow_offset),
        text,
        font=font,
        fill=WATERMARK_SHADOW_COLOR,
    )

    # Maandishi (nyeupe)
    draw.text(
        (text_x, text_y),
        text,
        font=font,
        fill=WATERMARK_TEXT_COLOR,
    )

    # ── Unganisha ──────────────────────────────────────────
    img = Image.alpha_composite(img, watermark_layer)

    # ── Hifadhi ────────────────────────────────────────────
    output = BytesIO()
    content_type = getattr(image_file, "content_type", "image/jpeg")

    if content_type == "image/jpeg" or original_format.upper() == "JPEG":
        img = img.convert("RGB")
        img.save(
            output,
            format="JPEG",
            quality=95,
            subsampling=0,
            optimize=True,
        )
    elif content_type == "image/png" or original_format.upper() == "PNG":
        img.save(output, format="PNG", optimize=True)
    elif content_type == "image/webp" or original_format.upper() == "WEBP":
        img.save(output, format="WEBP", quality=90, method=6)
    else:
        try:
            img.save(output, format=original_format, quality=95)
        except Exception:
            img.save(output, format="PNG", optimize=True)

    output.seek(0)
    return output