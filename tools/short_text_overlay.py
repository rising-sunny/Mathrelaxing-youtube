"""
Genera PNG transparentes de texto para shorts 9:16 (timed captions).

Además del texto por video, dibuja SIEMPRE dos elementos de marca/conversión:
  - un bug persistente con el handle del canal (reconocimiento en el feed)
  - un CTA de suscripción temporizado (el canal no pedía la suscripción en
    ningún lado: ~29.8k vistas orgánicas -> 45 subs)

    python tools/short_text_overlay.py \
        --outdir output/shorts_clifford/overlay \
        --frames 600 --fps 60 --res-w 1080 --res-h 1920

Opcional: --captions-json para no hardcodear el texto por video.
    [{"t0":0.0,"t1":3.2,"lines":[{"text":"A FLAT TORUS","font":"mid","color":[255,255,255]}]}]
"""
from __future__ import annotations

import argparse
import json
import os
from PIL import Image, ImageDraw, ImageFont

DEFAULT_HANDLE = "@MathRelaxing"
DEFAULT_CTA = "SUBSCRIBE FOR DAILY MATH"


def font(path, size, fallback=None):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        if fallback:
            try:
                return ImageFont.truetype(fallback, size)
            except OSError:
                pass
        return ImageFont.load_default()


def shadow_text(draw, xy, text, fnt, fill, shadow=(0, 0, 0, 220), off=3):
    x, y = xy
    for dx, dy in ((off, off), (off // 2, off // 2), (-1, 1)):
        draw.text((x + dx, y + dy), text, font=fnt, fill=shadow)
    draw.text((x, y), text, font=fnt, fill=fill)


def centered_text(draw, y, text, fnt, rgb, alpha, W, off=4):
    """Dibuja texto centrado horizontalmente con sombra, a opacidad `alpha` (0-1)."""
    if alpha <= 0.01 or not text:
        return
    bbox = draw.textbbox((0, 0), text, font=fnt)
    x = (W - (bbox[2] - bbox[0])) // 2
    col = (*rgb, int(255 * alpha))
    sh = (0, 0, 0, int(200 * alpha))
    shadow_text(draw, (x, y), text, fnt, col, shadow=sh, off=off)


def alpha_for_window(t, t0, t1, fade=0.35):
    """Opacity 0–1 with fade in/out inside [t0, t1]."""
    if t < t0 or t > t1:
        return 0.0
    if t < t0 + fade:
        return (t - t0) / fade
    if t > t1 - fade:
        return (t1 - t) / fade
    return 1.0


def default_captions(fonts):
    """Captions de ejemplo (Clifford Torus) — reemplazables con --captions-json."""
    return [
        (0.0, 3.2, [
            ("A FLAT TORUS", fonts["mid"], (255, 255, 255)),
            ("IN 4 DIMENSIONS", fonts["mid"], (100, 210, 255)),
        ]),
        (3.0, 6.5, [
            ("T² ⊂ S³ ⊂ R⁴", fonts["math"], (255, 210, 90)),
            ("stereographic shadow", fonts["small"], (180, 185, 195)),
        ]),
        (6.2, 1e9, [
            ("CLIFFORD TORUS", fonts["big"], (255, 255, 255)),
            ("#MathRelaxing", fonts["small"], (140, 200, 255)),
        ]),
    ]


def load_captions(path, fonts):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for blk in data:
        lines = [
            (
                ln["text"],
                fonts.get(str(ln.get("font", "mid")), fonts["mid"]),
                tuple(ln.get("color", [255, 255, 255])),
            )
            for ln in blk.get("lines", [])
        ]
        out.append((float(blk["t0"]), float(blk["t1"]), lines))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--frames", type=int, default=600)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--res-w", type=int, default=1080)
    ap.add_argument("--res-h", type=int, default=1920)
    ap.add_argument("--captions-json", default=None,
                    help="JSON con los bloques de texto del video (evita hardcodear)")
    ap.add_argument("--handle", default=DEFAULT_HANDLE,
                    help="Bug de marca persistente arriba (vacío para omitir)")
    ap.add_argument("--no-handle", action="store_true")
    ap.add_argument("--cta-text", default=DEFAULT_CTA,
                    help="CTA de suscripción en pantalla")
    ap.add_argument("--no-cta", action="store_true")
    ap.add_argument("--cta-start", type=float, default=None,
                    help="Segundo de inicio del CTA (default: 45%% de la duración)")
    ap.add_argument("--cta-end", type=float, default=None,
                    help="Segundo de fin del CTA (default: 85%% de la duración)")
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    W, H = a.res_w, a.res_h
    dur = a.frames / a.fps

    fonts = {
        "big": font(r"C:\Windows\Fonts\segoeuib.ttf", 64),
        "mid": font(r"C:\Windows\Fonts\segoeuib.ttf", 48),
        "math": font(r"C:\Windows\Fonts\cambria.ttc", 40, r"C:\Windows\Fonts\constan.ttf"),
        "small": font(r"C:\Windows\Fonts\segoeui.ttf", 28),
        "cta": font(r"C:\Windows\Fonts\segoeuib.ttf", 44),
        "handle": font(r"C:\Windows\Fonts\segoeui.ttf", 30),
    }

    captions = load_captions(a.captions_json, fonts) if a.captions_json else default_captions(fonts)

    # Ventana del CTA: por defecto en el tramo satisfactorio del loop, no al final.
    cta_t0 = a.cta_start if a.cta_start is not None else dur * 0.45
    cta_t1 = a.cta_end if a.cta_end is not None else dur * 0.85
    show_cta = not a.no_cta and bool(a.cta_text.strip()) and cta_t1 > cta_t0
    show_handle = not a.no_handle and bool((a.handle or "").strip())

    # Zonas seguras para Shorts: arriba libre (UI abajo/derecha).
    y_handle = int(H * 0.045)
    y_cta = int(H * 0.72)

    for i in range(a.frames):
        t = i / a.fps
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 1) Bug de marca persistente (reconocimiento de canal)
        if show_handle:
            centered_text(draw, y_handle, a.handle, fonts["handle"], (215, 225, 240), 0.62, W, off=3)

        # 2) Captions del video
        for t0, t1, lines in captions:
            a_op = alpha_for_window(t, t0, min(t1, dur + 0.1), fade=0.4)
            if a_op <= 0.01:
                continue
            y = int(H * 0.10)
            for text, fnt, rgb in lines:
                centered_text(draw, y, text, fnt, rgb, a_op, W, off=4)
                y += int(fnt.size * 1.35)

        # 3) CTA de suscripción temporizado
        if show_cta:
            a_cta = alpha_for_window(t, cta_t0, cta_t1, fade=0.5)
            centered_text(draw, y_cta, a.cta_text, fonts["cta"], (255, 235, 120), a_cta, W, off=4)

        img.save(os.path.join(a.outdir, f"{i:04d}.png"))

        if i % 60 == 0 or i == a.frames - 1:
            print(f"[text_overlay] {i + 1}/{a.frames}")

    print(f"[text_overlay] DONE -> {a.outdir}")
    print(f"[text_overlay] handle={'on' if show_handle else 'off'} "
          f"cta={'on' if show_cta else 'off'} ({cta_t0:.1f}s-{cta_t1:.1f}s)")


if __name__ == "__main__":
    main()
