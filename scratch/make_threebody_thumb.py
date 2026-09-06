"""
Thumbnail Three-Body Figure-8 — minimalista + expresión, poco solape.
YouTube 1280×720.
"""
import os
import sys
import numpy as np
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageFilter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from paths import font_path, thumbnail_path  # noqa: E402
FRAMES_DIR = os.path.join(REPO, "output", "threebody_1h", "frames")
OUTDIR = os.path.join(REPO, "output", "threebody_1h")
FRAME = "0450.png"
TW, TH = 1280, 720


def load_composition(path, zoom=1.35, shift_x=0.08):
    """Zoom suave; un poco de aire a la izquierda para el texto."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    cw, ch = int(w / zoom), int(h / zoom)
    cx = w // 2 - int(cw * shift_x)
    cy = h // 2
    left = max(0, min(w - cw, cx - cw // 2))
    top = max(0, min(h - ch, cy - ch // 2))
    crop = img.crop((left, top, left + cw, top + ch))
    return crop.resize((TW, TH), Image.Resampling.LANCZOS)


def boost(img):
    img = ImageEnhance.Contrast(img).enhance(1.35)
    img = ImageEnhance.Color(img).enhance(1.55)
    img = ImageEnhance.Brightness(img).enhance(1.12)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=2))
    return img


def soft_left_fade(img, strength=0.38, width_frac=0.36):
    arr = np.asarray(img).astype(np.float32)
    _, w, _ = arr.shape
    x = np.linspace(0, 1, w, dtype=np.float32)
    t = np.clip(x / width_frac, 0, 1)
    fade = 1.0 - strength * (1.0 - t) ** 2
    arr *= fade[None, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def draw_text_shadow(draw, text, xy, font, fill, shadow=(0, 0, 0), offset=3):
    x, y = xy
    draw.text((x + offset, y + offset), text, font=font, fill=shadow)
    draw.text((x + offset // 2, y + offset // 2), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


def main():
    frame_path = os.path.join(FRAMES_DIR, FRAME)
    if not os.path.exists(frame_path):
        # fallback a cualquier frame
        for name in sorted(os.listdir(FRAMES_DIR)):
            if name.endswith(".png"):
                frame_path = os.path.join(FRAMES_DIR, name)
                break
    if not os.path.exists(frame_path):
        print("No hay frames")
        sys.exit(1)

    os.makedirs(OUTDIR, exist_ok=True)
    base = boost(load_composition(frame_path))

    clean = os.path.join(OUTDIR, "threebody_thumbnail.jpg")
    base.save(clean, quality=95, optimize=True)
    print(f"Clean -> {clean}")

    img = soft_left_fade(base.copy())
    draw = ImageDraw.Draw(img)

    try:
        font_hour = ImageFont.truetype(font_path("bold"), 72)
        font_focus = ImageFont.truetype(font_path("bold"), 42)
        font_title = ImageFont.truetype(font_path("regular"), 26)
        font_math = ImageFont.truetype(font_path("math"), 28, index=0)
        font_def = ImageFont.truetype(font_path("regular"), 20)
    except OSError:
        font_hour = font_focus = font_title = font_math = font_def = ImageFont.load_default()

    mx, my = 48, 42

    draw_text_shadow(draw, "1 HOUR", (mx, my), font_hour, (255, 255, 255), offset=3)
    y = my + 82
    # Cian del body 0 — acento del figure-8
    draw_text_shadow(draw, "DEEP FOCUS", (mx, y), font_focus, (40, 220, 255), offset=2)

    line_y = y + 58
    draw.rectangle([mx + 1, line_y, mx + 1 + 96, line_y + 2], fill=(40, 220, 255))

    y = line_y + 16
    draw_text_shadow(draw, "3-BODY FIGURE-8", (mx, y), font_title, (200, 200, 210), offset=2)

    y = y + 38
    # Newton gravity for equal masses
    math_line = "m\u2081 = m\u2082 = m\u2083  \u00b7  G m\u00b2 / r\u00b2"
    draw_text_shadow(draw, math_line, (mx, y), font_math, (255, 210, 90), offset=2)

    y = y + 40
    draw_text_shadow(
        draw, "Moore choreography  \u221e", (mx, y), font_def, (150, 155, 170), offset=1
    )

    text_jpg = os.path.join(OUTDIR, "threebody_thumbnail_text.jpg")
    text_png = os.path.join(OUTDIR, "threebody_thumbnail_text.png")
    img.save(text_jpg, quality=95, optimize=True)
    img.save(text_png)
    print(f"Text  -> {text_jpg}")
    print(f"PNG   -> {text_png}")


if __name__ == "__main__":
    main()
