"""Espiral de Sacks — los primos formando curvas que nadie sabe explicar.

Cada entero n va en coordenadas polares con radio sqrt(n) y angulo 2*pi*sqrt(n).
Asi los cuadrados perfectos caen alineados sobre un eje y, sobre todo, los
primos se acomodan en arcos curvos en vez de repartirse al azar. Cada arco
corresponde a un polinomio cuadratico rico en primos (el de Euler, n^2+n+41,
es el mas marcado).

Los compuestos van como polvo tenue y los primos brillantes: el contraste es el
punto, porque muestra que el orden lo ponen los primos y no la espiral.

La camara se abre a ritmo constante mientras entran mas numeros, asi que el
disco mantiene su tamano aparente y lo que se ve es la estructura repitiendose
a toda escala.

    python scenes/prime_spiral.py -- --frames 900 --res 1920 --name shorts_primes --format 9:16
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
NAME = arg("--name", "shorts_primes")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
NMAX = int(arg("--nmax", 150_000))      # mas arriba el disco satura y las curvas se pierden
NMIN = int(arg("--nmin", 300))          # con que cantidad de numeros abre
FILL = float(arg("--fill", 0.46))       # radio del disco como fraccion del ancho
EXPOSURE = float(arg("--exposure", 1.25))
GLOW = float(arg("--glow", 0.35))
DUST = float(arg("--dust", 0.030))      # brillo de los compuestos, relativo al primo
TARGET = float(arg("--target", 1.35))   # puntos por pixel a los que se calibra el brillo

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
DUST_COL = np.array([0.22, 0.38, 0.95])    # compuestos: indigo apagado
EULER_COL = np.array([0.45, 1.00, 0.95])   # el polinomio de Euler, por encima
PRIME_COL = np.array([1.00, 0.86, 0.46])   # primos: oro claro


def sieve(n):
    """Criba de Eratostenes: mascara booleana de primos hasta n inclusive."""
    is_p = np.ones(n + 1, dtype=bool)
    is_p[:2] = False
    for p in range(2, int(n ** 0.5) + 1):
        if is_p[p]:
            is_p[p * p::p] = False
    return is_p


def euler_points(vmax):
    """Los valores enteros de n^2+n+41 y el arco que los une.

    Es el polinomio generador de primos mas famoso: da 40 primos seguidos
    (n = 0..39). Sobre la espiral de Sacks sus valores caen en un arco suave,
    asi que dibujarlo muestra de un vistazo por que los primos se alinean.

    Solo enteros: la curva continua t^2+t+41 no sirve para dibujar, porque el
    angulo 2*pi*sqrt(v) da una vuelta entera por cada unidad de t y el trazo se
    desparrama en radios en vez de seguir el arco.
    """
    n_top = int((-1 + np.sqrt(max(1.0, 4.0 * vmax - 163.0))) / 2.0)
    if n_top < 1:
        return None, None
    n = np.arange(0, n_top + 1, dtype=np.float64)
    v = n * n + n + 41.0
    v = v[v <= vmax]
    if len(v) < 2:
        return None, None
    ix, iy = polar(v)
    # el arco: segmentos rectos entre puntos consecutivos, subdivididos
    t = np.linspace(0.0, 1.0, 24)[None, :]
    ax = (ix[:-1, None] * (1 - t) + ix[1:, None] * t).ravel()
    ay = (iy[:-1, None] * (1 - t) + iy[1:, None] * t).ravel()
    return (ix, iy), (ax, ay)


def polar(v):
    """Coordenadas de Sacks: radio sqrt(v), angulo 2*pi*sqrt(v)."""
    r = np.sqrt(v)
    a = 2.0 * np.pi * r
    return r * np.cos(a), r * np.sin(a)


def splat(x, y, col, amp, canvas):
    """Acumula puntos con reparto bilineal en un buffer float."""
    inside = (x > 0) & (x < W - 1) & (y > 0) & (y < H - 1)
    x, y = x[inside], y[inside]
    if not len(x):
        return
    a = amp[inside] if isinstance(amp, np.ndarray) else np.full(len(x), amp)
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - x0, y - y0
    for dx, dy, wt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                       (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        idx = (y0 + dy) * W + (x0 + dx)
        g = wt * a
        for c in range(3):
            canvas[:, :, c].reshape(-1)[:] += np.bincount(
                idx, weights=g * col[c], minlength=W * H)


def main():
    print(f"[primes] cribando hasta {NMAX:,}...")
    is_prime = sieve(NMAX)
    n = np.arange(NMAX + 1, dtype=np.float64)
    root = np.sqrt(n)
    ang = 2.0 * np.pi * root
    px, py = root * np.cos(ang), root * np.sin(ang)
    prime_idx = np.flatnonzero(is_prime)
    comp_idx = np.flatnonzero(~is_prime)[2:]        # descarta 0 y 1
    print(f"[primes] {FRAMES} frames | {W}x{H} | {len(prime_idx):,} primos hasta {NMAX:,}")

    scale_note = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3"]
    events = []
    cx, cy = W * 0.5, H * 0.5
    ratio = (NMAX / NMIN) ** (1.0 / max(1, FRAMES - 1))   # crecimiento exponencial
    decade = -1

    for f in range(FRAMES):
        cur = int(min(NMAX, NMIN * ratio ** f))
        # el disco llega hasta sqrt(cur): la escala lo mantiene encuadrado
        s = (W * FILL) / np.sqrt(cur)

        # El disco mantiene su area en pantalla mientras entran 3000x mas
        # numeros: sin compensar, el arranque queda negro y el final saturado.
        density = cur / (np.pi * (W * FILL) ** 2)
        amp = float(np.clip(TARGET / max(density, 1e-9), 1.0, 90.0))

        canvas = np.zeros((H, W, 3), dtype=np.float32)
        ci = comp_idx[comp_idx <= cur]
        splat(px[ci] * s + cx, -py[ci] * s + cy, DUST_COL, amp * DUST, canvas)
        pi = prime_idx[prime_idx <= cur]
        splat(px[pi] * s + cx, -py[pi] * s + cy, PRIME_COL, amp, canvas)

        # el hilo de Euler por encima: la curva continua tenue y sus enteros brillantes
        pts, arc = euler_points(cur)
        if pts is not None:
            ax_, ay_ = arc
            splat(ax_ * s + cx, -ay_ * s + cy, EULER_COL, amp * 0.30, canvas)
            ix, iy = pts
            splat(ix * s + cx, -iy * s + cy, EULER_COL, amp * 4.0, canvas)

        canvas = gaussian_filter(canvas, (0.55, 0.55, 0)) + GLOW * gaussian_filter(canvas, (1.6, 1.6, 0))
        rgb = 1.0 - np.exp(-EXPOSURE * canvas)
        img = BG + (255.0 - BG) * rgb
        Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        # un golpe por cada decada de numeros que entra
        d = int(np.log10(max(cur, 1)))
        if d != decade:
            decade = d
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": round(min(0.95, 0.6 + 0.08 * len(events)), 2)})

        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[primes] {f + 1}/{FRAMES}  n={cur:,}  primos={len(pi):,}")

    if len(events) < 6:
        for j in range(8):
            events.append({"frame": int(j * FRAMES / 8), "note": scale_note[j % 8],
                           "intensity": 0.8})
        events.sort(key=lambda e: e["frame"])

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[primes] Eventos: {len(events)} -> {EVENTS_PATH}")
    print(f"[primes] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
