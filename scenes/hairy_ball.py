"""Teorema de la bola peluda — un campo vectorial tangente sobre la esfera.

Se peinan 4.000 lineas de flujo sobre una esfera con el campo

    v(p) = alfa * (a - (a.p) p)  +  beta * (a x p)

es decir, una componente meridional que empuja hacia el eje mas una zonal que
lo hace girar: de ahi las espirales. El campo se anula EXACTAMENTE en p = +-a,
y eso no es una eleccion desafortunada del campo sino algo inevitable: por el
teorema de la bola peluda, todo campo vectorial tangente y continuo sobre una
esfera tiene al menos un cero. En la atmosfera terrestre eso significa que en
todo momento hay al menos un punto sin viento horizontal.

El color codifica |v|, asi que los dos ceros se leen solos: la velocidad cae a
cero justo donde convergen las espirales.

Loop exacto por doble periodicidad: cada linea de flujo se precalcula con 360
pasos y el destello avanza 0.4 pasos por frame, o sea 360 pasos en 900 frames
(una vuelta completa), mientras la esfera gira 2*pi en el mismo ciclo.

    python scenes/hairy_ball.py -- --frames 900 --res 1920 --name shorts_hairyball --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_hairyball")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
N_LINES = int(arg("--lines", 22000))
STEPS = int(arg("--steps", 360))        # muestras por linea de flujo
TAIL = int(arg("--tail", 16))           # largo del destello
ALPHA = float(arg("--alpha", 0.85))     # peso meridional
BETA = float(arg("--beta", 1.55))       # peso zonal (giro)
DT = float(arg("--dt", 0.0125))
TILT = float(arg("--tilt", 0.42))       # inclinacion del eje, para ver el polo
FILL = float(arg("--fill", 0.455))
EXPOSURE = float(arg("--exposure", 5.5))
GLOW = float(arg("--glow", 0.55))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

if FMT == "9:16":
    H, W = RES, int(round(RES * 9 / 16))
else:
    W, H = RES, int(round(RES * 9 / 16))
W -= W % 2
H -= H % 2

BG = np.array([9, 12, 30], dtype=np.float64)
SLOW = np.array([1.00, 0.78, 0.26])     # |v| ~ 0 : oro, junto a los ceros
FAST = np.array([0.28, 0.92, 1.00])     # |v| maximo: cian, en el ecuador
AXIS = np.array([0.0, 0.0, 1.0])


def field(p):
    """v = alfa*(a - (a.p)p) + beta*(a x p). Tangente a la esfera por construccion."""
    d = p @ AXIS
    merid = AXIS[None, :] - d[:, None] * p
    zonal = np.cross(np.broadcast_to(AXIS, p.shape), p)
    return ALPHA * merid + BETA * zonal


def fibonacci_sphere(n):
    """Reparto casi uniforme: evita el amontonamiento en los polos de lat/lon."""
    i = np.arange(n) + 0.5
    phi = np.arccos(1.0 - 2.0 * i / n)
    theta = np.pi * (1.0 + 5.0 ** 0.5) * i
    return np.stack([np.sin(phi) * np.cos(theta),
                     np.sin(phi) * np.sin(theta),
                     np.cos(phi)], axis=1)


def trace():
    """Integra las lineas de flujo una sola vez. Devuelve (STEPS, N, 3) y |v|."""
    p = fibonacci_sphere(N_LINES)
    pts = np.empty((STEPS, N_LINES, 3), dtype=np.float32)
    spd = np.empty((STEPS, N_LINES), dtype=np.float32)
    for s in range(STEPS):
        pts[s] = p
        v = field(p)
        spd[s] = np.linalg.norm(v, axis=1)
        # RK2 sobre la esfera, renormalizando: el error de salirse del manifold
        # se acumula rapido con Euler simple
        mid = p + 0.5 * DT * v
        mid /= np.linalg.norm(mid, axis=1, keepdims=True)
        p = p + DT * field(mid)
        p /= np.linalg.norm(p, axis=1, keepdims=True)
    return pts, spd


def main():
    print(f"[hairy] trazando {N_LINES} lineas x {STEPS} pasos...")
    PTS, SPD = trace()
    SPD /= SPD.max()
    print(f"[hairy] {FRAMES} frames | {W}x{H} | |v| minimo {SPD.min():.4f} (los dos ceros)")

    offs = (np.arange(N_LINES) * 7919) % STEPS          # desfases repartidos
    scale = W * FILL
    cx, cy = W * 0.5, H * 0.5
    ct, st = np.cos(TILT), np.sin(TILT)
    scale_note = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3"]
    events = []

    for f in range(FRAMES):
        # 360 pasos en 900 frames: el destello da una vuelta entera por ciclo
        head = offs + f * (STEPS / FRAMES)
        ang = 2.0 * np.pi * f / FRAMES
        ca, sa = np.cos(ang), np.sin(ang)

        canvas = np.zeros((H, W, 3), dtype=np.float32)
        for k in range(TAIL):
            idx = (head - k).astype(np.int64) % STEPS
            p = PTS[idx, np.arange(N_LINES)]
            s = SPD[idx, np.arange(N_LINES)]

            # giro sobre el eje del campo, despues inclinacion hacia la camara
            x = p[:, 0] * ca - p[:, 1] * sa
            y = p[:, 0] * sa + p[:, 1] * ca
            z = p[:, 2]
            y2 = y * ct - z * st
            z2 = y * st + z * ct

            front = y2 < 0.0                       # la camara mira por -y
            fade = (1.0 - k / TAIL) ** 1.6
            amp = np.where(front, 1.0, 0.16) * fade * (0.35 + 0.65 * s)

            sx = x * scale + cx
            sy = -z2 * scale + cy
            ok = (sx > 0) & (sx < W - 1) & (sy > 0) & (sy < H - 1)
            xi, yi, si, ai = sx[ok], sy[ok], s[ok], amp[ok]
            col = SLOW[None, :] * (1 - si[:, None]) + FAST[None, :] * si[:, None]

            x0, y0 = np.floor(xi).astype(np.int64), np.floor(yi).astype(np.int64)
            fx, fy = xi - x0, yi - y0
            for dx, dy, wt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                               (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
                flat = (y0 + dy) * W + (x0 + dx)
                g = wt * ai
                for c in range(3):
                    canvas[:, :, c].reshape(-1)[:] += np.bincount(
                        flat, weights=g * col[:, c], minlength=W * H)

        canvas = gaussian_filter(canvas, (0.6, 0.6, 0)) + GLOW * gaussian_filter(canvas, (3.0, 3.0, 0))
        rgb = 1.0 - np.exp(-EXPOSURE * canvas / TAIL * 6.0)
        img = BG + (255.0 - BG) * rgb
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[hairy] {f + 1}/{FRAMES}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[hairy] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
