"""600-cell — el politopo regular de 4 dimensiones, rotando en 4D. numpy puro.

Es el analogo tetradimensional del icosaedro: 120 vertices sobre la 3-esfera,
720 aristas, y 600 celdas tetraedricas regulares. No cabe en 3D, asi que se lo
proyecta estereograficamente desde S^3, que es lo que curva las aristas en
arcos.

La rotacion es isoclina (mismo angulo en los planos xy y zw): los vertices se
desplazan a lo largo de fibras de Hopf, que es el movimiento mas fluido que
admite S^3. El angulo barre 0..2pi, asi que el loop cierra exacto.

El color codifica la cuarta coordenada w: cian = lejos en w, oro = cerca del
polo de proyeccion. Literalmente se ve la dimension que falta.

    python scenes/cell600_4d.py -- --frames 900 --res 1920 --name shorts_600cell --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import os
import sys
from itertools import permutations

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_600cell")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
SAMPLES = int(arg("--samples", 200))    # puntos por arista (arcos continuos)
SCALE = float(arg("--scale", 0.420))    # zoom de la proyeccion
EXPOSURE = float(arg("--exposure", 2.2))
GLOW = float(arg("--glow", 0.55))       # halo alrededor del nucleo del trazo

# Cerca de w=1 la proyeccion estereografica diverge: se desvanece el trazo en
# vez de dejarlo escapar al infinito.
W_FADE0, W_FADE1 = 0.72, 0.955

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

BG = np.array([10, 13, 32], dtype=np.float64)
# Paleta por w (la cuarta coordenada): azul profundo -> cian -> oro.
# Tres paradas y no dos: con una sola interpolacion el grueso de los puntos
# cae en el medio y todo se lava en gris.
COLD = np.array([0.16, 0.42, 1.00])     # w ~ -1: lejos del polo
MID = np.array([0.30, 0.95, 1.00])      # w ~  0
WARM = np.array([1.00, 0.74, 0.24])     # w ~ +1: cerca del polo de proyeccion


def vertices_600cell():
    """Los 120 vertices: 8 + 16 + 96 (permutaciones pares), todos en S^3."""
    phi = (1 + 5 ** 0.5) / 2
    V = []
    for i in range(4):
        for s in (1.0, -1.0):
            v = [0.0] * 4
            v[i] = s
            V.append(v)
    for a in (0.5, -0.5):
        for b in (0.5, -0.5):
            for c in (0.5, -0.5):
                for d in (0.5, -0.5):
                    V.append([a, b, c, d])
    base = [phi / 2, 0.5, 1 / (2 * phi), 0.0]

    def even(p):
        n = sum(1 for i in range(4) for j in range(i + 1, 4) if p[i] > p[j])
        return n % 2 == 0

    for perm in set(permutations(range(4))):
        if not even(perm):
            continue
        for s0 in (1.0, -1.0):
            for s1 in (1.0, -1.0):
                for s2 in (1.0, -1.0):
                    vals = [s0 * base[0], s1 * base[1], s2 * base[2], 0.0]
                    v = [0.0] * 4
                    for k in range(4):
                        v[perm[k]] = vals[k]
                    V.append(v)
    return np.unique(np.round(np.array(V), 9), axis=0)


def edges_of(V):
    """Aristas = pares a distancia minima (1/phi). Deben salir 720."""
    D = np.linalg.norm(V[:, None, :] - V[None, :, :], axis=2)
    d = D[D > 1e-6].min()
    i = np.arange(len(V))
    return np.argwhere((np.abs(D - d) < 1e-6) & (i[:, None] < i[None, :]))


def arc_samples(V, E, n):
    """Muestrea cada arista como geodesica en S^3 (slerp): de ahi salen los arcos."""
    a, b = V[E[:, 0]], V[E[:, 1]]
    omega = np.arccos(np.clip((a * b).sum(axis=1), -1, 1))[:, None]
    t = np.linspace(0.0, 1.0, n)[None, :, None]
    so = np.sin(omega)[:, None, :]
    p = (np.sin((1 - t) * omega[:, None, :]) * a[:, None, :]
         + np.sin(t * omega[:, None, :]) * b[:, None, :]) / so
    return p.reshape(-1, 4)


def splat(P4, canvas):
    """Proyecta, colorea por w y acumula con reparto bilineal."""
    w = P4[:, 3]
    keep = w < W_FADE1
    P4 = P4[keep]
    w = w[keep]

    xyz = P4[:, :3] / (1.0 - w)[:, None]
    sx = W * SCALE
    x = xyz[:, 0] * sx + W * 0.5
    y = -xyz[:, 1] * sx + H * 0.5

    inside = (x > 0) & (x < W - 1) & (y > 0) & (y < H - 1)
    x, y, w = x[inside], y[inside], w[inside]
    if not len(x):
        return

    # desvanecido cerca del polo + realce de los trazos que quedan al frente
    fade = np.clip((W_FADE1 - w) / (W_FADE1 - W_FADE0), 0.0, 1.0) ** 1.5
    depth = 1.0 / (1.0 + 2.2 * np.abs(xyz[inside, 2]))
    amp = fade * (0.50 + 0.50 * depth)

    tw = np.clip((w + 1.0) / 1.6, 0.0, 1.0)[:, None]
    lo = np.clip(tw * 2.0, 0.0, 1.0)
    hi = np.clip(tw * 2.0 - 1.0, 0.0, 1.0)
    col = (COLD * (1 - lo) + MID * lo) * (1 - hi) + WARM * hi

    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - x0, y - y0
    for dx, dy, wt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                       (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        idx = (y0 + dy) * W + (x0 + dx)
        g = wt * amp
        for c in range(3):
            canvas[:, :, c].reshape(-1)[:] += np.bincount(
                idx, weights=g * col[:, c], minlength=W * H)


def main():
    V = vertices_600cell()
    E = edges_of(V)
    assert len(V) == 120 and len(E) == 720, f"600-cell mal construido: {len(V)}v {len(E)}e"
    P0 = arc_samples(V, E, SAMPLES)
    for (i, j, ang) in ((0, 2, 0.553), (1, 3, 0.907), (0, 3, 0.318)):
        c0, s0 = np.cos(ang), np.sin(ang)
        P0[:, i], P0[:, j] = P0[:, i] * c0 - P0[:, j] * s0, P0[:, i] * s0 + P0[:, j] * c0
    print(f"[600cell] {FRAMES} frames | {W}x{H} | {len(V)} vertices, {len(E)} aristas"
          f" | {len(P0):,} puntos/frame")

    scale_note = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3"]
    events = []

    for f in range(FRAMES):
        th = 2.0 * np.pi * f / FRAMES          # periodo exacto -> loop sin costura
        c, s = np.cos(th), np.sin(th)
        R = P0.copy()
        # rotacion isoclina: mismo angulo en los planos xy y zw
        R[:, 0], R[:, 1] = P0[:, 0] * c - P0[:, 1] * s, P0[:, 0] * s + P0[:, 1] * c
        R[:, 2], R[:, 3] = P0[:, 2] * c - P0[:, 3] * s, P0[:, 2] * s + P0[:, 3] * c

        canvas = np.zeros((H, W, 3), dtype=np.float32)
        splat(R, canvas)
        # nucleo nitido + halo: da cuerpo a trazos que si no serian de 1 pixel
        canvas = gaussian_filter(canvas, (0.7, 0.7, 0)) + GLOW * gaussian_filter(canvas, (3.2, 3.2, 0))
        # respuesta filmica: satura suave donde los arcos se cruzan
        rgb = 1.0 - np.exp(-EXPOSURE * canvas)
        img = BG + (255.0 - BG) * rgb
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        # 8 golpes: el 600-cell vuelve sobre si mismo varias veces por vuelta
        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.85})

        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[600cell] {f + 1}/{FRAMES}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[600cell] Eventos: {len(events)} -> {EVENTS_PATH}")
    print(f"[600cell] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
