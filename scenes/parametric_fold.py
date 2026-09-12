"""Plegado parametrico: una hoja de puntos doblada y enrollada por una formula.

No hay simulacion. Cada punto de una grilla (x, y) se manda al plano por una
cadena de expresiones y listo: no hay estado, no hay integracion, no hay
vecinos. Es la familia de los "one-liner" de Processing.

La receta que hace la filigrana es que las dos direcciones de la grilla NO
hagan lo mismo: la lenta (y) barre el angulo y dibuja el arco, la rapida (x)
mete una oscilacion de frecuencia alta que apila curvas casi encima y deja el
peinado. Si las dos van parecido, sale una mancha solida.

    a = 7.2 y                    barrido angular, algo mas de una vuelta
    s = sin(50x) cos(6.8y)       el peine
    r = 20 + 46y + 15 sin(2.6a - 6*pi*T) + 12 s
    c = a + 0.55 sin(1.4a - 2*pi*T) + 0.3 s - 2*pi*T
    (u, v) = (r sin c, (r + 10 s) cos c)

LOOP EXACTO por construccion: T va de 0 a 1 a lo largo del clip y todos los
terminos temporales son 2*pi por un entero, asi que en T=1 la figura vuelve
identica a T=0. La rotacion global es exactamente una vuelta.

La expresion es propia. La tecnica es publica y esta muy documentada, pero las
formulas que circulan en video son obra de quien las escribio: esta se diseno
aca, cambiando la ley de angulo y la envolvente, no los coeficientes de otra.

    python scenes/parametric_fold.py -- --frames 900 --res 1920 --name shorts_fold --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import os
import sys

import numpy as np
from PIL import Image
from matplotlib.colors import hsv_to_rgb
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_fold")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
GX = int(arg("--gx", 900))              # direccion rapida: el peine
GY = int(arg("--gy", 420))              # direccion lenta: el barrido
GAIN = float(arg("--gain", 1.0))
FILL = float(arg("--fill", 0.92))       # cuanto del cuadro ocupa la figura

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

TAU = 2.0 * np.pi
_i = np.arange(GX * GY)
FX = (_i % GX).astype(np.float64) / GX
SY = (_i // GX).astype(np.float64) / GY
del _i


def fold(T):
    """(u, v) del plegado. T va de 0 a 1 en el ciclo completo."""
    a = SY * 7.2
    s = np.sin(FX * 50.0) * np.cos(SY * 6.8)
    r = 20.0 + 46.0 * SY + 15.0 * np.sin(2.6 * a - 3.0 * TAU * T) + 12.0 * s
    c = a + 0.55 * np.sin(1.4 * a - TAU * T) + 0.3 * s - TAU * T
    return r * np.sin(c), (r + 10.0 * s) * np.cos(c)


def splat(acc, x, y, col):
    ok = (x >= 0) & (x < W - 1) & (y >= 0) & (y < H - 1)
    x, y, col = x[ok], y[ok], col[ok]
    if not len(x):
        return
    ix, iy = x.astype(np.int64), y.astype(np.int64)
    fx, fy = (x - ix).astype(np.float32), (y - iy).astype(np.float32)
    base = iy * W + ix
    flat = acc.reshape(-1, 3)
    for off, wt in ((0, (1 - fx) * (1 - fy)), (1, fx * (1 - fy)),
                    (W, (1 - fx) * fy), (W + 1, fx * fy)):
        idx = base + off
        for ch in range(3):
            flat[:, ch] += np.bincount(idx, weights=wt * col[:, ch],
                                       minlength=flat.shape[0])


def main():
    # Escala fija para todo el clip: si se recalcula por frame, la figura
    # "respira" de tamano y se nota el enganche del loop.
    ex = 0.0
    for T in np.linspace(0.0, 1.0, 24, endpoint=False):
        u, v = fold(T)
        ex = max(ex, np.percentile(np.abs(u), 99.7) / (W / 2),
                 np.percentile(np.abs(v), 99.7) / (H / 2))
    scale = FILL / ex
    print(f"[fold] {GX}x{GY} = {GX * GY} puntos  escala {scale:.2f}")

    # El color va con la posicion a lo largo de la cinta, fijo en el tiempo:
    # asi las bandas se leen como una misma superficie girando.
    col = hsv_to_rgb(np.stack([(SY * 0.70 + 0.48) % 1.0,
                               np.full(GX * GY, 0.88),
                               np.ones(GX * GY)], 1)).astype(np.float32)
    col *= (0.55 + 0.55 * np.cos(FX * 50.0)).astype(np.float32)[:, None]
    col *= (0.24 * GAIN)

    scale_note = ["D2", "F2", "A2", "C3", "D3", "F3", "A3", "C4"]
    events = []
    cx, cy = W / 2.0, H / 2.0

    for f in range(FRAMES):
        T = f / FRAMES                      # el ciclo cierra: T=1 es T=0
        u, v = fold(T)
        img = np.zeros((H, W, 3), dtype=np.float32)
        splat(img, cx + u * scale, cy + v * scale, col)
        img = 1.0 - np.exp(-2.1 * np.maximum(img, 0.0))
        img = np.clip(img + 0.55 * gaussian_filter(img, (1.6, 1.6, 0)), 0.0, 1.0)
        Image.fromarray((img * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[fold] {f + 1}/{FRAMES}  T = {T:.3f}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "points": GX * GY, "loop": True}, jf)
    print(f"[fold] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
