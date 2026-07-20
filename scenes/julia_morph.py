"""Julia set morph — loop continuo, numpy puro (sin Blender).

El parametro c recorre un CIRCULO CERRADO en el plano complejo, asi que el
fractal se deforma y vuelve exactamente al punto de partida: loop sin corte.

Contrato con render/build_clip.py --engine numpy:
    python scenes/julia_morph.py -- --frames 900 --res 1920 --name shorts_julia --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json

Por que fractales: es la familia con mejor swipe rate del canal (43.1% vs 33.6%
de promedio) y solo se habia hecho UN video (1329 vistas).
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
RES = int(arg("--res", 1920))          # altura
NAME = arg("--name", "shorts_julia")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
MAX_ITER = int(arg("--max-iter", 220))
# Radio del circulo que recorre c. Cambiarlo da una familia visual distinta.
C_RADIUS = float(arg("--c-radius", 0.7885))
C_PHASE = float(arg("--c-phase", 0.0))
ZOOM = float(arg("--zoom", 1.35))

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
# ancho/alto pares para libx264
W -= W % 2
H -= H % 2


def make_palette():
    """Paleta suave tipo nebulosa: azul profundo -> cian -> ambar -> blanco."""
    stops = [
        (0.00, (6, 8, 26)),
        (0.28, (18, 62, 140)),
        (0.50, (34, 168, 200)),
        (0.70, (240, 176, 62)),
        (0.86, (255, 232, 150)),
        (1.00, (255, 255, 255)),
    ]
    lut = np.zeros((256, 3), dtype=np.float64)
    for i in range(256):
        t = i / 255.0
        for j in range(len(stops) - 1):
            t0, c0 = stops[j]
            t1, c1 = stops[j + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                lut[i] = np.array(c0) * (1 - f) + np.array(c1) * f
                break
    return lut.astype(np.uint8)


PALETTE = make_palette()


def julia_frame(c):
    """Escape-time vectorizado con mascara activa + coloreo suave."""
    aspect = W / H
    y, x = np.mgrid[0:H, 0:W]
    zx = (x / (W - 1) - 0.5) * 2.0 * ZOOM * aspect
    zy = (y / (H - 1) - 0.5) * 2.0 * ZOOM
    Z = zx + 1j * zy

    out = np.zeros(Z.shape, dtype=np.float64)
    active = np.ones(Z.shape, dtype=bool)

    for n in range(MAX_ITER):
        ZA = Z[active]
        ZA = ZA * ZA + c
        Z[active] = ZA
        escaped = np.abs(ZA) > 4.0
        if escaped.any():
            idx = np.flatnonzero(active)[escaped]
            # coloreo suave: n + 1 - log(log|z|)/log 2
            mag = np.abs(ZA[escaped])
            out.flat[idx] = n + 1.0 - np.log(np.log(mag)) / np.log(2.0)
            active.flat[idx] = False
        if not active.any():
            break

    # normalizar (los puntos que nunca escapan quedan en 0 = interior oscuro)
    m = out.max()
    norm = out / m if m > 0 else out
    norm = np.power(norm, 0.55)  # realza el detalle de los bordes
    idx8 = np.clip((norm * 255.0), 0, 255).astype(np.uint8)
    return PALETTE[idx8]


def main():
    print(f"[julia] {FRAMES} frames | {W}x{H} | max_iter={MAX_ITER} | r={C_RADIUS}")
    events = []
    prev_ratio = None

    for f in range(FRAMES):
        theta = 2.0 * np.pi * (f / FRAMES) + C_PHASE
        c = C_RADIUS * complex(np.cos(theta), np.sin(theta))

        rgb = julia_frame(c)
        Image.fromarray(rgb, mode="RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png")
        )

        # Evento de sonificacion: "masa" luminosa del fractal en pantalla.
        # (No usamos el area interior: con radio ~0.79 el conjunto es dendritico
        # y no tiene interior, asi que esa metrica seria siempre 0.)
        mass = float((rgb.max(axis=2) > 110).mean())
        if prev_ratio is None or abs(mass - prev_ratio) > 0.004:
            events.append({
                "t": round(f / FPS, 3),
                "frame": f,
                "value": round(mass, 4),
                "c_re": round(c.real, 4),
                "c_im": round(c.imag, 4),
            })
            prev_ratio = mass

        if f % 60 == 0 or f == FRAMES - 1:
            print(f"[julia] {f + 1}/{FRAMES}  c=({c.real:+.3f},{c.imag:+.3f})  mass={mass:.3f}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[julia] Eventos: {len(events)} -> {EVENTS_PATH}")
    print(f"[julia] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
