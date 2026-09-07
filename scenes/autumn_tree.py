"""Arbol recursivo al atardecer — pieza de ambiente, no de divulgacion.

Registro distinto al resto del repo: paleta calida, imagen figurativa y cero
formulas. La matematica sigue estando (el arbol es un sistema de ramificacion
recursivo con razon de acortamiento fija), pero aca es medio y no tema.

Todo el movimiento es periodico en FRAMES, asi que el loop cierra exacto: el
viento mece las ramas con una sinusoide y las hojas se desprenden con fase
escalonada, de modo que en cualquier instante hay unas en el arbol y otras
cayendo. No hay principio ni final visibles.

    python scenes/autumn_tree.py -- --frames 900 --res 1920 --name shorts_autumn --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_autumn")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
SEED = int(arg("--seed", 20260907))
DEPTH = int(arg("--depth", 10))
SS = int(arg("--ss", 2))
SWAY = float(arg("--sway", 0.055))      # amplitud del viento, en radianes

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
SW, SH = W * SS, H * SS

# Paleta del atardecer: violeta arriba, rosa al medio, ambar en el horizonte.
SKY_STOPS = [
    (0.00, (46, 26, 58)),
    (0.30, (96, 44, 74)),
    (0.52, (168, 74, 74)),
    (0.66, (226, 126, 62)),
    (0.74, (246, 176, 92)),
    (0.78, (250, 205, 140)),
]
HORIZON = 0.78                 # altura del horizonte en fraccion de H
WATER = (44, 24, 46)
SILHOUETTE = (26, 13, 28)
SUN = (255, 232, 176)
LEAF_COLS = [(236, 118, 46), (214, 74, 52), (244, 168, 62),
             (250, 208, 128), (188, 62, 74), (232, 146, 70)]


def sky():
    """Degradado vertical + sol + reflejo en el agua."""
    img = np.zeros((SH, SW, 3), dtype=np.float64)
    ys = np.linspace(0.0, 1.0, SH)
    stops = SKY_STOPS
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        m = (ys >= t0) & (ys <= t1)
        if not m.any():
            continue
        f = ((ys[m] - t0) / (t1 - t0))[:, None]
        img[m, :, :] = (np.array(c0) * (1 - f) + np.array(c1) * f)[:, None, :]
    img[ys > stops[-1][0], :, :] = np.array(WATER)

    yy, xx = np.mgrid[0:SH, 0:SW]
    sun_x, sun_y, sun_r = SW * 0.42, SH * HORIZON, SW * 0.115
    d = np.hypot(xx - sun_x, yy - sun_y)
    disc = np.clip(1.0 - (d - sun_r) / (SW * 0.006), 0.0, 1.0)
    halo = np.exp(-((d / (sun_r * 3.1)) ** 2)) * 0.55
    for c in range(3):
        img[:, :, c] = img[:, :, c] * (1 - disc) + SUN[c] * disc
        img[:, :, c] = np.minimum(255.0, img[:, :, c] + SUN[c] * halo * 0.55)
    # reflejo: columna del sol sobre el agua, con bandas
    water = yy > SH * HORIZON
    band = (0.72 + 0.28 * np.cos(yy * 0.055)) * np.exp(-((xx - sun_x) / (SW * 0.17)) ** 2)
    for c in range(3):
        img[:, :, c] = np.where(water, np.minimum(255.0, img[:, :, c] + SUN[c] * band * 0.20),
                                img[:, :, c])
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def build_tree(rng, x, y, ang, length, width, depth):
    """Topologia fija del arbol. Las posiciones se recalculan por frame."""
    nodes = []   # (parent, ang_local, length, width, depth, phase)

    def rec(parent, ang_local, length, width, d):
        idx = len(nodes)
        nodes.append([parent, ang_local, length, width, d, rng.uniform(0, 2 * math.pi)])
        if d >= depth:
            return
        n = 2 if rng.random() < 0.78 else 3
        spread = rng.uniform(0.30, 0.52)
        for k in range(n):
            frac = (k / (n - 1) - 0.5) if n > 1 else 0.0
            a = frac * 2 * spread + rng.uniform(-0.10, 0.10)
            rec(idx, a, length * rng.uniform(0.68, 0.79), width * 0.70, d + 1)

    rec(-1, ang, length, width, 0)
    nodes[0][1] = ang
    return nodes


def tree_points(nodes, x0, y0, t):
    """Posiciones de cada rama en el instante t (0..1), con el mecido del viento."""
    n = len(nodes)
    ax = [0.0] * n
    px = [0.0] * n
    py = [0.0] * n
    for i, (parent, ang_l, length, width, d, phase) in enumerate(n[:6] for n in nodes):
        # el viento crece con la profundidad: el tronco casi no se mueve
        w = SWAY * (d / max(1, DEPTH)) ** 1.6 * math.sin(2 * math.pi * t + phase)
        if parent < 0:
            ax[i] = ang_l + w
            sx, sy = x0, y0
        else:
            ax[i] = ax[parent] + ang_l + w
            sx, sy = px[parent], py[parent]
        px[i] = sx + math.cos(ax[i]) * length
        py[i] = sy - math.sin(ax[i]) * length
    return px, py


def main():
    rng = random.Random(SEED)
    base = sky()

    # un arbol grande al frente y dos mas chicos al fondo, para dar profundidad
    trees = []
    specs = [
        (0.62, 0.985, SH * 0.185, SH * 0.0135, 1.00, 0),
        (0.20, 0.960, SH * 0.115, SH * 0.0080, 0.55, 1),
        (0.86, 0.950, SH * 0.098, SH * 0.0070, 0.42, 1),
    ]
    for fx, fy, ln, wd, dim, dsub in specs:
        r = random.Random(rng.randrange(1 << 30))
        nodes = build_tree(r, 0, 0, math.pi / 2 + r.uniform(-0.09, 0.09), ln, wd, DEPTH - dsub)
        trees.append((nodes, SW * fx, SH * fy, dim))

    # hojas: se cuelgan de las puntas y caen con fase escalonada
    leaves = []
    for ti, (nodes, _, _, dim) in enumerate(trees):
        tips = [i for i, nd in enumerate(nodes) if nd[4] >= DEPTH - 3]
        rr = random.Random(SEED + ti)
        for i in tips:
            if rr.random() < (0.42 if ti == 0 else 0.28):
                leaves.append({
                    "tree": ti, "node": i,
                    "phase": rr.random(),
                    "rad": SH * rr.uniform(0.0034, 0.0072) * (1.0 if ti == 0 else 0.7),
                    "col": LEAF_COLS[rr.randrange(len(LEAF_COLS))],
                    "drift": rr.uniform(-1.0, 1.0),
                    "spin": rr.uniform(0.5, 1.6),
                    "dim": dim,
                })
    print(f"[autumn] {FRAMES} frames | {W}x{H} (ss{SS}) | "
          f"{sum(len(t[0]) for t in trees)} ramas | {len(leaves)} hojas")

    scale_note = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3"]
    events = []
    fall_span = 0.42          # cuanto dura la caida, en fraccion del ciclo

    for f in range(FRAMES):
        t = f / FRAMES
        img = base.copy()
        dr = ImageDraw.Draw(img, "RGBA")

        pos = []
        for nodes, x0, y0, dim in trees:
            px, py = tree_points(nodes, x0, y0, t)
            pos.append((px, py))
            col = tuple(int(SILHOUETTE[c] + (WATER[c] - SILHOUETTE[c]) * (1 - dim) * 0.8)
                        for c in range(3))
            for i, nd in enumerate(nodes):
                parent = nd[0]
                sx, sy = (x0, y0) if parent < 0 else (px[parent], py[parent])
                wdt = max(1, int(nd[3] * (1.0 if dim > 0.9 else 0.75)))
                dr.line([sx, sy, px[i], py[i]], fill=col + (255,), width=wdt)

        for lf in leaves:
            ph = (t + lf["phase"]) % 1.0
            px, py = pos[lf["tree"]]
            ax_, ay_ = px[lf["node"]], py[lf["node"]]
            if ph < 1.0 - fall_span:
                cx, cy, a = ax_, ay_, 1.0
            else:
                u = (ph - (1.0 - fall_span)) / fall_span          # 0..1 cayendo
                cy = ay_ + (SH * 0.62) * u * u
                cx = ax_ + lf["drift"] * SW * 0.06 * u + math.sin(u * 6.2 * lf["spin"]) * SW * 0.012
                a = min(1.0, 2.6 * (1.0 - u))                     # se desvanece al final
            if a <= 0.02:
                continue
            r = lf["rad"]
            c = lf["col"]
            alpha = int(255 * a * (0.55 + 0.45 * lf["dim"]))
            dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c + (alpha,))

        if SS > 1:
            img = img.resize((W, H), Image.LANCZOS)
        img = img.filter(ImageFilter.GaussianBlur(0.4))
        img.save(os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.5})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[autumn] {f + 1}/{FRAMES}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[autumn] Eventos: {len(events)} -> {EVENTS_PATH}")
    print(f"[autumn] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
