"""Pila de arena abeliana — el fractal que nace de una sola regla, numpy puro.

Se apilan N granos en UNA celda. Toda celda con 4 o mas granos "colapsa" y
reparte uno a cada vecino. Se repite hasta que nadie tiene 4. El teorema
abeliano dice que el estado final no depende del orden de los colapsos: para
cada N hay una unica configuracion estable, y esa configuracion es un fractal.

La animacion muestra la sucesion de estados ESTABLES para N creciente (no el
transitorio, que es ruido): el fractal crece y se refina sin parar. La camara
sigue el radio de la pila, asi que el tamano aparente es constante y lo que se
ve es la estructura subdividiendose a toda escala.

    python scenes/abelian_sandpile.py -- --frames 900 --res 1920 --name shorts_sandpile --format 9:16
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
NAME = arg("--name", "shorts_sandpile")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
GRAINS = int(arg("--grains", 500_000))     # granos en el estado final
HOLD = int(arg("--hold", 45))              # frames de sostenido en el final

# El radio de la pila estable crece como ~0.36*sqrt(N); 0.42 deja margen para
# que ningun grano alcance el borde de la ventana de relajacion.
R_OF_N = 0.42
R_FLOOR = 14          # radio aparente minimo: al principio se ven los granos
PAD = 3

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

# 0 granos = fondo; 1 = indigo; 2 = ambar; 3 = oro claro (arena incandescente)
PALETTE = np.array([
    (10, 13, 32),
    (46, 38, 128),
    (232, 138, 32),
    (255, 226, 140),
], dtype=np.uint8)
BG = tuple(int(v) for v in PALETTE[0])

S = 2 * (int(R_OF_N * np.sqrt(GRAINS)) + 24) + 1
C = S // 2
# Los granos se agregan de a poco (~2*GRAINS/FRAMES por frame), asi que ningun
# sitio supera unos pocos miles: int16 alcanza y mueve la mitad de memoria que
# int32, que es lo que domina el costo del topple.
grid = np.zeros((S, S), dtype=np.int16)


def relax(radius):
    """Colapsa hasta que ninguna celda tenga 4 granos. Devuelve las rondas.

    Trabaja solo en la ventana [C-radius, C+radius]: el soporte de la pila
    estable nunca la excede, y acotarla es lo que hace viable el render.
    """
    lo, hi = C - radius, C + radius + 1
    sub = grid[lo:hi, lo:hi]
    rounds = 0
    while (sub >= 4).any():
        t = sub >> 2
        sub -= t << 2
        sub[1:, :] += t[:-1, :]
        sub[:-1, :] += t[1:, :]
        sub[:, 1:] += t[:, :-1]
        sub[:, :-1] += t[:, 1:]
        rounds += 1
    return rounds


def support_radius():
    """Radio (Chebyshev) del soporte actual, en celdas."""
    rows = np.flatnonzero(grid.any(axis=1))
    cols = np.flatnonzero(grid.any(axis=0))
    if not len(rows):
        return 1
    return int(max(rows[-1] - C, C - rows[0], cols[-1] - C, C - cols[0]))


def render(view_r):
    """Recorta la pila y la centra en el lienzo vertical."""
    lo, hi = C - view_r, C + view_r + 1
    sub = np.clip(grid[lo:hi, lo:hi], 0, 3)
    side = hi - lo
    # ampliar => NEAREST (se ven los granos uno a uno); reducir => BOX (antialias)
    resample = Image.NEAREST if side < W else Image.BOX
    tile = Image.fromarray(PALETTE[sub], "RGB").resize((W, W), resample)
    canvas = Image.new("RGB", (W, H), BG)
    canvas.paste(tile, (0, (H - W) // 2))
    return canvas


def main():
    print(f"[sandpile] {FRAMES} frames | {W}x{H} | {GRAINS:,} granos | grilla {S}x{S}")
    scale = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3", "C4"]
    events, placed, total_rounds, next_event_r = [], 0, 0, R_FLOOR

    grow = max(1, FRAMES - HOLD)
    for f in range(FRAMES):
        # N crece cuadraticamente => el radio (~sqrt(N)) crece lineal en pantalla
        p = min(1.0, (f + 1) / grow)
        target = max(1, int(GRAINS * p * p))
        if target > placed:
            grid[C, C] += np.int16(target - placed)
            placed = target
            total_rounds += relax(min(C - 1, int(R_OF_N * np.sqrt(target)) + 16))

        r = support_radius()
        view_r = max(r + PAD, R_FLOOR)
        render(view_r).save(os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        # un golpe cada vez que la pila gana ~35% de radio
        if r >= next_event_r:
            events.append({"frame": f, "note": scale[len(events) % len(scale)],
                           "intensity": round(min(0.95, 0.55 + 0.05 * len(events)), 2)})
            next_event_r = int(next_event_r * 1.35) + 1

        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[sandpile] {f + 1}/{FRAMES}  N={placed:,}  radio={r}  rondas={total_rounds:,}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[sandpile] Eventos: {len(events)} -> {EVENTS_PATH}")
    print(f"[sandpile] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
