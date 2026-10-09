import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


WATERMARK_TEXT = "SokoMkononi.co.tz"
WATERMARK_TEXT_COLOR = (255, 255, 255, 200)
WATERMARK_SHADOW_COLOR = (0, 0, 0, 150)
WATERMARK_FONT_SIZE = 28
WATERMARK_PADDING = 20


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


def add_watermark(image_file, text=None):
    if text is None:
        text = WATERMARK_TEXT

    img = Image.open(image_file)

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    width, height = img.size

    watermark_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_layer)

    font = get_font()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = width - text_width - WATERMARK_PADDING
    y = height - text_height - WATERMARK_PADDING

    shadow_offset = 2
    draw.text(
        (x + shadow_offset, y + shadow_offset),
        text,
        font=font,
        fill=WATERMARK_SHADOW_COLOR,
    )

    draw.text(
        (x, y),
        text,
        font=font,
        fill=WATERMARK_TEXT_COLOR,
    )

    watermarked = Image.alpha_composite(img, watermark_layer)

    content_type = getattr(image_file, "content_type", "image/jpeg")

    output = BytesIO()
    if content_type == "image/jpeg":
        watermarked = watermarked.convert("RGB")
        watermarked.save(output, format="JPEG", quality=90, optimize=True)
    else:
        watermarked.save(output, format="PNG", optimize=True)

    output.seek(0)
    return output