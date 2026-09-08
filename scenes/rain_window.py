"""Lluvia sobre un vidrio, con las luces de la calle desenfocadas detras.

Pieza de ambiente para el canal chico. La gracia no son las gotas sino lo que
hacen con la luz: una gota de agua sobre un vidrio funciona como lente, y como
es convexa invierte lo que hay detras. Por eso cada gota se pinta muestreando
el fondo MAS ABAJO de su posicion, no en su posicion: es lo que hace que se lea
como agua y no como puntos brillantes.

El fondo se dibuja en un buffer chico y se agranda. No es un atajo: esta
fuera de foco, asi que la resolucion sobra y el desenfoque sale gratis.

Todo el movimiento es periodico en FRAMES, asi que el loop cierra exacto: las
luces derivan con senoidales de ciclo entero y cada gota que resbala tiene su
propia fase, de modo que en cualquier instante hay unas quietas y otras
cayendo. No hay principio ni final visibles.

    python scenes/rain_window.py -- --frames 900 --res 1920 --name shorts_rain --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, zoom

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_rain")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
SEED = int(arg("--seed", 90721))
N_BOKEH = int(arg("--bokeh", 27))
N_STILL = int(arg("--still", 260))      # gotas quietas
N_RUN = int(arg("--runners", 34))       # gotas que resbalan
TRAIL = int(arg("--trail", 13))         # gotitas que deja cada resbalon
DOWN = int(arg("--down", 5))            # submuestreo del fondo desenfocado

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
BW, BH = W // DOWN, H // DOWN

NIGHT_TOP = np.array([8, 14, 26], dtype=np.float64)
NIGHT_BOT = np.array([16, 22, 34], dtype=np.float64)
# Luces de calle: ambar dominante, con algo de rosa y un par de frias.
LIGHTS = [(255, 176, 92), (255, 150, 84), (255, 205, 140), (255, 126, 110),
          (255, 190, 110), (140, 190, 255), (255, 168, 96)]

rng = np.random.default_rng(SEED)

BOKEH = []
for _ in range(N_BOKEH):
    BOKEH.append({
        "x": rng.uniform(-0.1, 1.1), "y": rng.uniform(-0.05, 1.05),
        "r": rng.uniform(0.045, 0.135),
        "col": np.array(LIGHTS[rng.integers(len(LIGHTS))], dtype=np.float64),
        "amp": rng.uniform(0.35, 1.0),
        # deriva lenta, en ciclos enteros para no romper el loop
        "dx": rng.uniform(0.008, 0.030), "dy": rng.uniform(0.004, 0.018),
        "mx": int(rng.integers(1, 3)), "my": int(rng.integers(1, 3)),
        "px": rng.uniform(0, 6.28), "py": rng.uniform(0, 6.28),
    })

STILL = {
    "x": rng.uniform(0.0, 1.0, N_STILL),
    "y": rng.uniform(0.0, 1.0, N_STILL),
    "r": rng.uniform(0.006, 0.026, N_STILL) ** 0.95,
}
RUN = []
for _ in range(N_RUN):
    RUN.append({
        "x": rng.uniform(0.03, 0.97),
        "y0": rng.uniform(-0.25, 0.15),
        "r": rng.uniform(0.018, 0.038),
        "phase": rng.random(),
        "wob": rng.uniform(-1.0, 1.0),
        "speed": rng.uniform(0.85, 1.35),
    })


def backdrop(t):
    """Luces desenfocadas, en baja resolucion: el desenfoque sale gratis."""
    ys = np.linspace(0, 1, BH)[:, None, None]
    img = np.repeat(NIGHT_TOP[None, None, :] + (NIGHT_BOT - NIGHT_TOP)[None, None, :] * ys,
                    BW, axis=1)
    yy, xx = np.mgrid[0:BH, 0:BW]
    xn, yn = xx / BW, yy / BH
    for b in BOKEH:
        cx = b["x"] + b["dx"] * math.sin(2 * math.pi * b["mx"] * t + b["px"])
        cy = b["y"] + b["dy"] * math.cos(2 * math.pi * b["my"] * t + b["py"])
        d = np.hypot((xn - cx) * (BW / BH), yn - cy) / b["r"]
        # disco con borde suave: un bokeh real tiene el canto marcado
        disc = np.clip(1.0 - d ** 6, 0.0, 1.0) ** 0.55
        img += b["amp"] * disc[:, :, None] * b["col"][None, None, :] * 0.52
    img = gaussian_filter(img, (2.2, 2.2, 0))
    big = zoom(np.clip(img, 0, 245), (H / BH, W / BW, 1), order=1)
    return np.clip(big[:H, :W], 0, 245)


def clear_path(canvas, sharp, x, y_from, y_to, rad):
    """El reguero que deja la gota: limpia el vaho y deja ver nitido detras.

    Es el rasgo que hace leer la escena como un vidrio mojado; sin el, las
    gotas son solo puntos brillantes sobre un fondo borroso.
    """
    px, rw = x * W, rad * W * 1.5
    x0, x1 = int(max(0, px - rw * 2.2)), int(min(W, px + rw * 2.2 + 1))
    y0, y1 = int(max(0, y_from * H)), int(min(H, y_to * H))
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    across = np.exp(-((xx - px) / rw) ** 2)
    # se desvanece hacia arriba: el reguero se vuelve a empanar
    along = np.clip((yy - y0) / max(1.0, (y1 - y0) * 0.55), 0.0, 1.0) ** 1.3
    m = (across * along * 0.95)[:, :, None]
    canvas[y0:y1, x0:x1] = canvas[y0:y1, x0:x1] * (1 - m) + sharp[y0:y1, x0:x1] * m


def draw_drops(canvas, back, xs, ys, rs, gain):
    """Cada gota muestrea el fondo MAS ABAJO: la lente convexa invierte."""
    for x, y, r in zip(xs, ys, rs):
        px, py = x * W, y * H
        rad = r * W
        x0, x1 = int(max(0, px - rad - 2)), int(min(W, px + rad + 3))
        y0, y1 = int(max(0, py - rad - 2)), int(min(H, py + rad + 3))
        if x1 <= x0 or y1 <= y0:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d = np.hypot(xx - px, yy - py) / rad
        mask = np.clip(1.0 - d ** 3, 0.0, 1.0)
        if not mask.any():
            continue
        sy = int(np.clip(py + rad * 2.1, 0, H - 1))
        sx = int(np.clip(px, 0, W - 1))
        col = back[sy, sx] * gain + 9.0
        rim = np.clip(1.0 - np.abs(d - 0.86) / 0.17, 0.0, 1.0) ** 2 * mask
        hl = np.clip(1.0 - np.hypot(xx - (px - rad * 0.33), yy - (py - rad * 0.35))
                     / (rad * 0.30), 0, 1) ** 2
        m3 = mask[:, :, None]
        canvas[y0:y1, x0:x1] = (canvas[y0:y1, x0:x1] * (1 - m3)
                                + col[None, None, :] * m3
                                + rim[:, :, None] * col[None, None, :] * 0.55
                                + hl[:, :, None] * 58.0)


def main():
    print(f"[rain] {FRAMES} frames | {W}x{H} | fondo {BW}x{BH} | "
          f"{N_BOKEH} luces, {N_STILL} gotas, {N_RUN} resbalones")
    scale_note = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3"]
    events = []

    for f in range(FRAMES):
        t = f / FRAMES
        back = backdrop(t)
        # el vidrio empana lo que hay detras
        canvas = gaussian_filter(back, (16.0, 16.0, 0)) * 0.58 + 7.0
        sharp = gaussian_filter(back, (1.6, 1.6, 0)) * 0.95

        rx, ry, rr = [], [], []
        for d in RUN:
            u = (t * d["speed"] + d["phase"]) % 1.0
            y = d["y0"] + 1.35 * u * u          # acelera al caer
            if y > 1.12:
                continue
            clear_path(canvas, sharp, d["x"], max(0.0, d["y0"]), y, d["r"])
            x = d["x"] + 0.012 * d["wob"] * math.sin(u * 11.0)
            rx.append(x); ry.append(y); rr.append(d["r"])
            for k in range(1, TRAIL + 1):
                uk = max(0.0, u - k * 0.012)
                yk = d["y0"] + 1.35 * uk * uk
                if yk < -0.05:
                    break
                rx.append(d["x"] + 0.012 * d["wob"] * math.sin(uk * 11.0))
                ry.append(yk)
                rr.append(d["r"] * (0.62 - 0.35 * k / TRAIL))
        draw_drops(canvas, back, STILL["x"], STILL["y"], STILL["r"], 1.05)
        if rx:
            draw_drops(canvas, back, np.array(rx), np.array(ry), np.array(rr), 1.20)

        Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.45})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[rain] {f + 1}/{FRAMES}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[rain] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
