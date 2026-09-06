"""
Thumbnail Hopf Fibration — minimalista + más copy + expresión matemática.
YouTube 1280×720. Texto en zona negra (izq/arriba); gráfica a la derecha.
"""
import os
import sys
import numpy as np
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageFilter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from paths import font_path, thumbnail_path  # noqa: E402
FRAMES_DIR = os.path.join(REPO, "output", "hopf_1h", "frames")
OUTDIR = os.path.join(REPO, "output", "hopf_1h")
FRAME = "0400.png"

TW, TH = 1280, 720


def load_composition(path, zoom=1.65, shift_x=0.14):
    """Zoom + shift: Hopf a la derecha, aire negro a la izquierda para el texto."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    cw, ch = int(w / zoom), int(h / zoom)

    cx = w // 2 - int(cw * shift_x)
    cy = h // 2 - int(h * 0.01)
    left = max(0, min(w - cw, cx - cw // 2))
    top = max(0, min(h - ch, cy - ch // 2))

    crop = img.crop((left, top, left + cw, top + ch))
    return crop.resize((TW, TH), Image.Resampling.LANCZOS)


def boost(img):
    img = ImageEnhance.Contrast(img).enhance(1.22)
    img = ImageEnhance.Color(img).enhance(1.40)
    img = ImageEnhance.Brightness(img).enhance(1.06)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=100, threshold=2))
    return img


def soft_left_fade(img, strength=0.32, width_frac=0.40):
    """Viñeta suave solo bajo el bloque de texto."""
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
        print(f"No existe {frame_path}")
        sys.exit(1)

    os.makedirs(OUTDIR, exist_ok=True)

    base = boost(load_composition(frame_path, zoom=1.65, shift_x=0.14))

    clean_path = os.path.join(OUTDIR, "hopf_thumbnail.jpg")
    base.save(clean_path, quality=95, optimize=True)
    print(f"Clean -> {clean_path}")

    img = soft_left_fade(base.copy())
    draw = ImageDraw.Draw(img)

    # Fuentes: bold para impacto, regular/light para jerarquía
    try:
        font_hour = ImageFont.truetype(font_path("bold"), 72)
        font_focus = ImageFont.truetype(font_path("bold"), 42)
        font_title = ImageFont.truetype(font_path("regular"), 28)
        font_math = ImageFont.truetype(font_path("math"), 30, index=0)
        # fallback si cambria no carga con index
    except OSError:
        font_hour = font_focus = font_title = font_math = ImageFont.load_default()

    # Bloque superior-izquierdo (zona negra tras el shift)
    mx, my = 48, 42

    # 1) 1 HOUR — ancla visual
    draw_text_shadow(draw, "1 HOUR", (mx, my), font_hour, (255, 255, 255), offset=3)

    # 2) DEEP FOCUS — acento magenta (fibras)
    y = my + 82
    draw_text_shadow(draw, "DEEP FOCUS", (mx, y), font_focus, (210, 95, 255), offset=2)

    # 3) Raya fina de acento
    line_y = y + 58
    draw.rectangle([mx + 1, line_y, mx + 1 + 96, line_y + 2], fill=(200, 90, 255))

    # 4) Título del sistema
    y = line_y + 16
    draw_text_shadow(
        draw, "HOPF FIBRATION", (mx, y), font_title, (200, 200, 210), offset=2
    )

    # 5) Expresión matemática — la de la fibración de Hopf
    #    η : S³ → S²
    y = y + 40
    math_line = "\u03b7 : S\u00b3 \u2192 S\u00b2"  # η : S³ → S²
    draw_text_shadow(
        draw, math_line, (mx, y), font_math, (170, 230, 255), offset=2
    )

    # 6) Definición breve (compacta, tipografía un poco menor)
    try:
        font_def = ImageFont.truetype(font_path("regular"), 20)
    except OSError:
        font_def = font_title
    y = y + 42
    draw_text_shadow(
        draw, "linked circles in S\u00b3", (mx, y), font_def, (140, 145, 160), offset=1
    )

    text_path = os.path.join(OUTDIR, "hopf_thumbnail_text.jpg")
    img.save(text_path, quality=95, optimize=True)
    print(f"Text  -> {text_path}")

    png_path = os.path.join(OUTDIR, "hopf_thumbnail_text.png")
    img.save(png_path)
    print(f"PNG   -> {png_path}")


if __name__ == "__main__":
    main()
