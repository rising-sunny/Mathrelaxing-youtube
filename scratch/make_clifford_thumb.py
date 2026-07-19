"""
Thumbnail Clifford Torus 4D — minimalista + expresión matemática.
YouTube 1280×720. Texto izq; toro a la derecha.
"""
import os
import sys
import numpy as np
from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageFilter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", "clifford_1h", "frames")
OUTDIR = os.path.join(REPO, "output", "clifford_1h")
FRAME = "0400.png"
TW, TH = 1280, 720


def load_composition(path, zoom=1.55, shift_x=0.12):
    """Zoom + shift: toro más a la derecha, aire negro a la izquierda."""
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
    img = ImageEnhance.Brightness(img).enhance(1.18)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.3, percent=120, threshold=2))
    return img


def soft_left_fade(img, strength=0.40, width_frac=0.42):
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
        for name in sorted(os.listdir(FRAMES_DIR)):
            if name.endswith(".png"):
                frame_path = os.path.join(FRAMES_DIR, name)
                break
    if not os.path.exists(frame_path):
        print("No hay frames")
        sys.exit(1)

    os.makedirs(OUTDIR, exist_ok=True)
    base = boost(load_composition(frame_path))

    clean = os.path.join(OUTDIR, "clifford_thumbnail.jpg")
    base.save(clean, quality=95, optimize=True)
    print(f"Clean -> {clean}")

    img = soft_left_fade(base.copy())
    draw = ImageDraw.Draw(img)

    try:
        font_hour = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 72)
        font_focus = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 42)
        font_title = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 26)
        font_math = ImageFont.truetype(r"C:\Windows\Fonts\cambria.ttc", 28, index=0)
        font_def = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 20)
    except OSError:
        try:
            font_hour = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 72)
            font_focus = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 42)
            font_title = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 26)
            font_math = ImageFont.truetype(r"C:\Windows\Fonts\constan.ttf", 28)
            font_def = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 20)
        except OSError:
            font_hour = font_focus = font_title = font_math = font_def = ImageFont.load_default()

    mx, my = 48, 42

    # 1 HOUR
    draw_text_shadow(draw, "1 HOUR", (mx, my), font_hour, (255, 255, 255), offset=3)

    # DEEP FOCUS — acento cian/oro del toro
    y = my + 82
    draw_text_shadow(draw, "DEEP FOCUS", (mx, y), font_focus, (80, 200, 255), offset=2)

    # Raya
    line_y = y + 58
    draw.rectangle([mx + 1, line_y, mx + 1 + 96, line_y + 2], fill=(80, 200, 255))

    # Título
    y = line_y + 16
    draw_text_shadow(draw, "CLIFFORD TORUS", (mx, y), font_title, (200, 200, 210), offset=2)

    # Expresión: T² ⊂ S³ ⊂ ℝ⁴
    y = y + 38
    math_line = "T\u00b2 \u2282 S\u00b3 \u2282 R\u2074"
    draw_text_shadow(draw, math_line, (mx, y), font_math, (255, 210, 100), offset=2)

    # Subtítulo
    y = y + 40
    draw_text_shadow(
        draw, "4D flat torus \u00b7 stereo S\u00b3\u2192R\u00b3",
        (mx, y), font_def, (145, 150, 165), offset=1,
    )

    text_jpg = os.path.join(OUTDIR, "clifford_thumbnail_text.jpg")
    text_png = os.path.join(OUTDIR, "clifford_thumbnail_text.png")
    img.save(text_jpg, quality=95, optimize=True)
    img.save(text_png)
    print(f"Text  -> {text_jpg}")
    print(f"PNG   -> {text_png}")


if __name__ == "__main__":
    main()
