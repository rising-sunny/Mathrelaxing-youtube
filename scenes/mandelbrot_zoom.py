"""Mandelbrot — zoom infinito hacia el Valle de los Caballitos de Mar, numpy puro.

Escape-time vectorizado con mascara activa + coloreo suave (smooth iteration
count) y paleta ciclica que rota lentamente. La ventana compleja se encoge
exponencialmente hacia un punto famoso del borde, revelando espirales y
mini-Mandelbrots que se repiten a toda escala.

    python scenes/mandelbrot_zoom.py -- --frames 900 --res 1920 --name shorts_mandelbrot --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import os
import sys

import numpy as np
from PIL import Image

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_mandelbrot")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
DOWN = int(arg("--down", 2))            # submuestreo interno (velocidad)

# Punto de destino (Seahorse Valley — zoom clasico, rico en espirales)
CX = -0.743643887037158704752191506114774
CY = 0.131825904205311970493132056385139
HH0 = 1.25          # media-altura inicial (muestra casi todo el set)
HH_END = 5.0e-7     # media-altura final -> zoom total 2.5e6x, seguro en doble precision
ITER0, ITER1 = 220, 900

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

if FMT == "9:16":
    H = RES
    W = int(round(RES * 9 / 16))
else:
    W = RES
    H = int(round(RES * 9 / 16))
W -= W % 2
H -= H % 2
IW, IH = W // DOWN, H // DOWN          # lienzo interno


def make_palette():
    """Paleta CICLICA rica (para bandas de escape que se repiten sin costura)."""
    stops = [
        (0.00, (8, 12, 40)),
        (0.14, (12, 60, 150)),
        (0.30, (30, 170, 220)),
        (0.44, (220, 245, 255)),
        (0.56, (255, 210, 90)),
        (0.68, (235, 120, 30)),
        (0.80, (150, 30, 90)),
        (0.90, (60, 20, 110)),
        (1.00, (8, 12, 40)),           # cierra el ciclo
    ]
    lut = np.zeros((1024, 3), dtype=np.float64)
    for i in range(1024):
        t = i / 1024.0
        for j in range(len(stops) - 1):
            t0, c0 = stops[j]
            t1, c1 = stops[j + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                lut[i] = np.array(c0) * (1 - f) + np.array(c1) * f
                break
    return lut.astype(np.uint8)


PALETTE = make_palette()
NP = len(PALETTE)


def mandel(hh, max_iter, hue_shift):
    aspect = IW / IH
    yy, xx = np.mgrid[0:IH, 0:IW].astype(np.float64)
    cr = CX + (xx / (IW - 1) - 0.5) * 2.0 * hh * aspect
    ci = CY + (yy / (IH - 1) - 0.5) * 2.0 * hh
    C = cr + 1j * ci
    Z = np.zeros_like(C)
    out = np.zeros(C.shape, dtype=np.float64)
    active = np.ones(C.shape, dtype=bool)
    for n in range(max_iter):
        Za = Z[active]
        Za = Za * Za + C[active]
        Z[active] = Za
        esc = (Za.real * Za.real + Za.imag * Za.imag) > 256.0
        if esc.any():
            idx = np.flatnonzero(active)[esc]
            mag = np.abs(Za[esc])
            out.flat[idx] = n + 1.0 - np.log(np.log(mag)) / np.log(2.0)
            active.flat[idx] = False
        if not active.any():
            break
    # interior (nunca escapa) queda en 0 -> negro/azul profundo
    cyc = (out * 0.028 + hue_shift) % 1.0
    cyc[out == 0] = 0.0
    idx8 = np.clip(cyc * (NP - 1), 0, NP - 1).astype(np.int32)
    rgb = PALETTE[idx8]
    rgb[out == 0] = PALETTE[0]
    return rgb


def main():
    print(f"[mandel] {FRAMES} frames | {W}x{H} (interno {IW}x{IH}) | zoom {HH0:.2f} -> {HH_END:.1e}")
    ratio = (HH_END / HH0) ** (1.0 / max(1, FRAMES - 1))
    events = []
    scale = ["C2", "Eb2", "G2", "C3", "Eb3", "G3", "C4"]
    hh = HH0
    for f in range(FRAMES):
        p = f / max(1, FRAMES - 1)
        max_iter = int(ITER0 + (ITER1 - ITER0) * p)
        hue = 0.12 * p                        # deriva de color lenta
        rgb = mandel(hh, max_iter, hue)
        Image.fromarray(rgb, "RGB").resize((W, H), Image.BICUBIC).save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        # Evento cada vez que cruzamos otra decada de zoom (pulso de descenso)
        if f == 0 or int(-np.log10(hh)) != int(-np.log10(hh / ratio)):
            events.append({"frame": f, "note": scale[len(events) % len(scale)],
                           "intensity": 0.85})
        hh *= ratio
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[mandel] {f + 1}/{FRAMES}  hh={hh:.2e}  iter={max_iter}")

    if len(events) < 6:
        for j in range(8):
            events.append({"frame": int(j * FRAMES / 8), "note": scale[j % len(scale)],
                           "intensity": 0.8})
        events.sort(key=lambda e: e["frame"])

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[mandel] Eventos: {len(events)} -> {EVENTS_PATH}")
    print(f"[mandel] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
