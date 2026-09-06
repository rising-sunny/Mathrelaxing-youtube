"""Overlay matematico (Computer Modern / LaTeX) para la pila de arena abeliana.

Dos capas sobre las bandas oscuras que deja el disco en 9:16:

  estatica   la regla de colapso y la identidad que da nombre al modelo
  dinamica   el contador de granos ya colocados (cambia por frame)

Todo va en la banda oscura de arriba: el disco ocupa el cuadrado central y
la banda de abajo queda para el CTA de brand_cta.

El contador replica exactamente la curva de la escena: N(f) = GRAINS * p^2 con
p = min(1, (f+1)/(FRAMES-HOLD)). Si cambia la escena, cambia aca.

    python tools/sandpile_math_overlay.py --frames 900 --outdir output/shorts_sandpile/overlay \
        --res-w 1080 --res-h 1920 --grains 500000 --hold 45
"""

from __future__ import annotations

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

plt.rcParams["mathtext.fontset"] = "cm"     # Computer Modern: el look de LaTeX
plt.rcParams["font.family"] = "serif"
plt.rcParams["text.usetex"] = False

# Regla de colapso: un sitio con 4 o mas granos reparte uno a cada vecino.
RULE = r"$z_v \geq 4 \ \Longrightarrow\ z_v \mapsto z_v - 4$"
RULE_2 = r"$z_u \mapsto z_u + 1 \quad \forall\, u \sim v$"
# Los operadores de adicion conmutan: de ahi "abeliano".
ABELIAN = r"$a_i\,a_j = a_j\,a_i \quad \mathrm{(the\ order\ never\ matters)}$"


def _panel(res_w, res_h, items):
    """Panel RGBA transparente con textos mathtext. items: (texto, y, color, size)."""
    dpi = 100
    fig = plt.figure(figsize=(res_w / dpi, res_h / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)
    for text, y, color, size in items:
        ax.text(0.5, y, text, fontsize=size, ha="center", va="center", color=color)
    fig.canvas.draw()
    img = Image.fromarray(np.asarray(fig.canvas.buffer_rgba()), mode="RGBA")
    plt.close(fig)
    return img


def generate(frames, outdir, res_w, res_h, grains, hold):
    os.makedirs(outdir, exist_ok=True)
    k = res_w / 1080.0                       # las tipografias se fijan para 1080 de ancho

    # --- Capa estatica: banda oscura de arriba (y de figura, 0 = abajo) ---
    # El disco ocupa el cuadrado central (0.219 a 0.781), asi que todo el texto
    # vive por encima de 0.80. Abajo solo va el CTA que quema brand_cta.
    static = _panel(res_w, res_h, [
        (RULE,     0.925, (1.0, 1.0, 1.0, 0.96), 30 * k),
        (RULE_2,   0.884, (1.0, 0.90, 0.55, 0.88), 26 * k),
        (ABELIAN,  0.846, (0.66, 0.76, 1.0, 0.85), 22 * k),
    ])

    # --- Capa dinamica: contador de granos, justo debajo del disco ---
    dpi = 100
    fig = plt.figure(figsize=(res_w / dpi, res_h / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)
    counter = ax.text(0.5, 0.806, "", fontsize=25 * k, ha="center", va="center",
                      color=(1.0, 0.86, 0.42, 0.95))

    grow = max(1, frames - hold)
    print(f"[math] Generando {frames} overlays {res_w}x{res_h}...")
    for f in range(frames):
        p = min(1.0, (f + 1) / grow)
        n = max(1, int(grains * p * p))
        # separador fino (\,): estilo ISO, mas limpio que la coma en Computer Modern
        digits = f"{n:,}".replace(",", r"\,")
        counter.set_text(rf"$N = {digits}\ \mathrm{{grains}}$")
        fig.canvas.draw()
        dyn = Image.fromarray(np.asarray(fig.canvas.buffer_rgba()), mode="RGBA")
        Image.alpha_composite(static, dyn).save(os.path.join(outdir, f"{f:04d}.png"))
        if (f + 1) % 100 == 0 or f == frames - 1:
            print(f"[math] {f + 1}/{frames}")

    plt.close(fig)
    print(f"[math] Listo -> {outdir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=900)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--res-w", type=int, default=1080)
    ap.add_argument("--res-h", type=int, default=1920)
    ap.add_argument("--grains", type=int, default=500_000)
    ap.add_argument("--hold", type=int, default=45)
    a = ap.parse_args()
    generate(a.frames, a.outdir, a.res_w, a.res_h, a.grains, a.hold)


if __name__ == "__main__":
    main()
