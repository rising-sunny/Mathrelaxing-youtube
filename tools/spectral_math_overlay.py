"""
Overlay matemático elegante (Computer Modern / LaTeX) para spectral cymatics.

Optimizado: la fórmula estática se renderiza 1 vez; solo se regenera el bloque
dinámico inferior por frame.
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

plt.rcParams["mathtext.fontset"] = "cm"
plt.rcParams["font.family"] = "serif"
plt.rcParams["text.usetex"] = False

FORMULA = (
    r"$W(r,\theta,t)=\sum_{i=1}^{6}"
    r"A_i(t)\,\cos(k_i r-\omega_i t)"
    r"\,\cos(m_i\theta+\phi_i)$"
)

FORMULA_SUB = (
    r"$A_i \propto E_i(\omega)\ \ |\ \ "
    r"k_i = k_0\cdot i\ \ |\ \ "
    r"m_i = 2,3,4,5,7,9$"
)


def _render_text_panel(res_w: int, res_h: int, lines, y_positions, colors, sizes):
    """Renderiza un panel transparente con varios textos mathtext."""
    dpi = 100
    fig = plt.figure(figsize=(res_w / dpi, res_h / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)

    for text, y, color, size in zip(lines, y_positions, colors, sizes):
        ax.text(
            0.5, y, text,
            fontsize=size, ha="center", va="center",
            color=color, linespacing=1.4,
        )

    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    plt.close(fig)
    return Image.fromarray(buf, mode="RGBA")


def generate(events_path: str, outdir: str, res_w: int, res_h: int, fps: int = 30):
    with open(events_path, encoding="utf-8") as fh:
        meta = json.load(fh)
    events = meta["events"]
    n = len(events)
    os.makedirs(outdir, exist_ok=True)

    # --- Capa estática (fórmula) — una sola vez ---
    static = _render_text_panel(
        res_w, res_h,
        lines=[
            r"$\mathrm{Spectral\ Cymatics}$",
            FORMULA,
            FORMULA_SUB,
        ],
        y_positions=[0.93, 0.86, 0.79],
        colors=[
            (1, 1, 1, 0.55),
            (1, 1, 1, 0.92),
            (0.75, 0.88, 1.0, 0.78),
        ],
        sizes=[13, 12, 10],
    )

    # Figura reutilizable solo para el bloque dinámico
    dpi = 100
    fig = plt.figure(figsize=(res_w / dpi, res_h / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)
    t_vals = ax.text(
        0.5, 0.12, "",
        fontsize=11, ha="center", va="center",
        color=(1.0, 0.85, 0.35, 0.95),
        linespacing=1.45,
    )

    print(f"[math] Generando {n} overlays {res_w}x{res_h}...")
    for f, ev in enumerate(events):
        rms = float(ev.get("rms", 0.0))
        cent = float(ev.get("centroid", 0.0))
        onset = float(ev.get("onset", 0.0))
        bands = ev.get("bands", [0] * 6)
        t_s = float(ev.get("t_seconds", f / fps))

        a_str = r",\,".join(f"{0.12 + 0.88 * float(b):.2f}" for b in bands[:6])
        val = (
            rf"$t={t_s:5.2f}\,\mathrm{{s}}"
            rf"\ \ |\ \ \mathrm{{RMS}}={rms:0.2f}"
            rf"\ \ |\ \ \hat{{f}}={cent:0.2f}$"
            + "\n"
            + rf"$A_i=[{a_str}]$"
            + "\n"
            + rf"$\mathrm{{onset}}={onset:0.2f}$"
        )
        t_vals.set_text(val)
        fig.canvas.draw()
        dyn = Image.fromarray(np.asarray(fig.canvas.buffer_rgba()), mode="RGBA")

        # Combinar estático + dinámico (alpha max)
        out = Image.alpha_composite(static, dyn)
        out.save(os.path.join(outdir, f"{f:04d}.png"))

        if (f + 1) % 50 == 0 or f == n - 1:
            print(f"[math] {f + 1}/{n}")

    plt.close(fig)
    print(f"[math] Listo → {outdir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--res-w", type=int, default=576)
    ap.add_argument("--res-h", type=int, default=1024)
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    generate(a.events, a.outdir, a.res_w, a.res_h, a.fps)


if __name__ == "__main__":
    main()
