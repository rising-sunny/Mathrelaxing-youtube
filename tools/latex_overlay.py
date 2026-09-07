"""Overlay de texto matematico (Computer Modern / LaTeX) para cualquier escena.

Usa el mathtext de matplotlib con fontset "cm": tipografia de LaTeX sin
depender de una instalacion de LaTeX. Reemplaza a los overlays por escena, que
solo se diferenciaban en el texto.

La escena no se conoce aca: el build script arma un JSON con las lineas fijas y
(opcional) el texto por frame de una linea dinamica.

    {
      "scrim":   {"rgb": [10,13,32], "top": {"extent": 0.30, "strength": 0.9}},
      "static":  [{"text": "$x^2$", "y": 0.92, "rgba": [1,1,1,0.96], "size": 30}],
      "dynamic": {"y": 0.80, "rgba": [1,0.86,0.42,0.95], "size": 25,
                  "texts": ["$N = 1$", "$N = 2$", ...]}
    }

`y` va en coordenadas de figura (0 = abajo, 1 = arriba) y `size` esta calibrado
para 1080 px de ancho; se reescala solo a otras resoluciones.

El "scrim" es un degradado opaco en los bordes, debajo del texto: sin el, sobre
una escena que llena el cuadro las formulas compiten con el dibujo y no se leen.
`extent` es que fraccion de la altura cubre y `strength` su opacidad maxima.

    python tools/latex_overlay.py --spec spec.json --outdir out/ --res-w 1080 --res-h 1920
"""

from __future__ import annotations

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

plt.rcParams["mathtext.fontset"] = "cm"     # Computer Modern: el look de LaTeX
plt.rcParams["font.family"] = "serif"
plt.rcParams["text.usetex"] = False

REF_WIDTH = 1080.0


def _figure(res_w, res_h):
    dpi = 100
    fig = plt.figure(figsize=(res_w / dpi, res_h / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)
    return fig, ax


def _snapshot(fig):
    fig.canvas.draw()
    return Image.fromarray(np.asarray(fig.canvas.buffer_rgba()), mode="RGBA")


def _scrim(spec, res_w, res_h):
    """Degradado desde los bordes, para que el texto se lea sobre escenas densas."""
    cfg = spec.get("scrim")
    if not cfg:
        return None
    rgb = np.array(cfg.get("rgb", [0, 0, 0]), dtype=np.float64)
    alpha = np.zeros((res_h, 1), dtype=np.float64)
    rows = np.arange(res_h)
    for side in ("top", "bottom"):
        band = cfg.get(side)
        if not band:
            continue
        n = max(1, int(band["extent"] * res_h))
        ramp = np.linspace(band["strength"], 0.0, n) ** 1.5
        idx = rows[:n] if side == "top" else rows[res_h - n:][::-1]
        alpha[idx, 0] = np.maximum(alpha[idx, 0], ramp)
    img = np.zeros((res_h, res_w, 4), dtype=np.uint8)
    img[:, :, :3] = rgb.astype(np.uint8)
    img[:, :, 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    return Image.fromarray(img, "RGBA")


def generate(spec, outdir, res_w, res_h):
    os.makedirs(outdir, exist_ok=True)
    k = res_w / REF_WIDTH

    # --- capa fija: se dibuja una sola vez ---
    fig, ax = _figure(res_w, res_h)
    for item in spec.get("static", []):
        ax.text(0.5, item["y"], item["text"], fontsize=item["size"] * k,
                ha="center", va="center", color=tuple(item["rgba"]))
    static = _snapshot(fig)
    plt.close(fig)

    scrim = _scrim(spec, res_w, res_h)
    if scrim is not None:
        static = Image.alpha_composite(scrim, static)

    dyn = spec.get("dynamic")
    if not dyn:
        static.save(os.path.join(outdir, "static.png"))
        print(f"[latex] Capa fija -> {outdir}/static.png")
        return

    texts = dyn["texts"]
    fig, ax = _figure(res_w, res_h)
    handle = ax.text(0.5, dyn["y"], "", fontsize=dyn["size"] * k,
                     ha="center", va="center", color=tuple(dyn["rgba"]))

    print(f"[latex] Generando {len(texts)} overlays {res_w}x{res_h}...")
    for f, text in enumerate(texts):
        handle.set_text(text)
        Image.alpha_composite(static, _snapshot(fig)).save(
            os.path.join(outdir, f"{f:04d}.png"))
        if (f + 1) % 100 == 0 or f == len(texts) - 1:
            print(f"[latex] {f + 1}/{len(texts)}")
    plt.close(fig)
    print(f"[latex] Listo -> {outdir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, help="JSON con las lineas del overlay")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--res-w", type=int, default=1080)
    ap.add_argument("--res-h", type=int, default=1920)
    a = ap.parse_args()
    with open(a.spec, encoding="utf-8") as fh:
        spec = json.load(fh)
    generate(spec, a.outdir, a.res_w, a.res_h)


if __name__ == "__main__":
    main()
