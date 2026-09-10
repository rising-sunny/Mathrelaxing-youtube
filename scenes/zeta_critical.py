"""La funcion zeta de Riemann sobre la franja critica, coloreada por fase.

Cada pixel es un numero complejo s = sigma + i t: el color es el ANGULO de
zeta(s) y el brillo su modulo. Donde zeta se anula todos los colores se juntan
en un punto, y esos puntos caen todos sobre la misma recta vertical,
Re(s) = 1/2. Eso es la hipotesis de Riemann, sin demostrar desde 1859.

zeta se define como una serie que solo converge para Re(s) > 1:

    zeta(s) = sum_{n>=1} n^(-s) = prod_p (1 - p^(-s))^(-1)

y se extiende al resto del plano por continuacion analitica. Aca se evalua con
Euler-Maclaurin, que da la continuacion directamente:

    zeta(s) = sum_{n<N} n^-s + N^-s/2 + N^(1-s)/(s-1)
              + sum_k B_2k/(2k)! (s)_{2k-1} N^(-s-2k+1)

Truco de costo: n^(-s) = n^(-sigma) * exp(-i t log n) SEPARA las variables, asi
que cada termino de la suma sobre la grilla es un producto externo de un vector
de columnas por uno de filas. La imagen alta completa sale en ~25 s en vez de
minutos.

La camara sube por la recta critica; cada cero destella al pasar por el centro
del cuadro y dispara una nota. NO es un loop: es un recorrido de t=8 a t=49.

    python scenes/zeta_critical.py -- --frames 900 --res 1920 --name shorts_zeta --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import math
import os
import sys

import numpy as np
from matplotlib.colors import hsv_to_rgb
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_zeta")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
SIG0 = float(arg("--sig0", -1.0))       # borde izquierdo en Re(s)
SIG1 = float(arg("--sig1", 2.0))        # borde derecho en Re(s)
EM_N = int(arg("--em-n", 48))           # corte de la suma de Euler-Maclaurin
EM_M = int(arg("--em-m", 8))            # terminos de correccion de Bernoulli

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

# Ceros no triviales: partes imaginarias, valores clasicos.  Se verifican
# numericamente al arrancar (|zeta| tiene que dar ~1e-10 en cada uno).
ZEROS = [14.134725142, 21.022039639, 25.010857580, 30.424876126, 32.935061588,
         37.586178159, 40.918719012, 43.327073281, 48.005150881, 49.773832478]

PPU = W / (SIG1 - SIG0)                 # pixeles por unidad del plano complejo
TWIN = H / PPU                          # alto de la ventana en unidades de t

# El encuadre se elige para que en el frame 0 ya se vea un cero arriba (los
# primeros medio segundo de un short son los que deciden), el primero cruce el
# centro a ~0.9 s y el octavo a ~13.8 s. El ritmo se acelera solo, porque los
# ceros se juntan al subir.
F_FIRST, F_LAST = 55, 830
RATE = (ZEROS[7] - ZEROS[0]) / (F_LAST - F_FIRST)     # unidades de t por frame
C0 = ZEROS[0] - F_FIRST * RATE                        # t en el centro, frame 0
TB0 = C0 - TWIN / 2                                   # t en el borde inferior

TMIN = TB0
TMAX = TB0 + RATE * (FRAMES - 1) + TWIN
TALL = int(round((TMAX - TMIN) * PPU))

BERNOULLI = [0.0, 1 / 6, -1 / 30, 1 / 42, -1 / 30, 5 / 66,
             -691 / 2730, 7 / 6, -3617 / 510]


def zeta_grid(sig, t):
    """zeta sobre la grilla (t, sigma) por Euler-Maclaurin, separando n^(-s)."""
    tot = np.zeros((len(t), len(sig)), dtype=np.complex128)
    for n in range(1, EM_N):
        ln = math.log(n)
        tot += np.exp(-1j * t * ln)[:, None] * np.exp(-sig * ln)[None, :]
    lnN = math.log(EM_N)
    s = sig[None, :] + 1j * t[:, None]
    tot += 0.5 * np.exp(-s * lnN) + np.exp((1 - s) * lnN) / (s - 1)
    poch = s.copy()
    for k in range(1, EM_M + 1):
        if k > 1:
            poch = poch * (s + 2 * k - 3) * (s + 2 * k - 2)
        tot += BERNOULLI[k] / math.factorial(2 * k) * poch * np.exp((-s - 2 * k + 1) * lnN)
    return tot


def colorize(z, sig):
    """Fase -> tono, modulo -> bandas de brillo.  Los ceros salen blancos."""
    m = np.abs(z)
    hue = (np.angle(z) + np.pi) / (2 * np.pi)
    # bandas suaves en potencias de 2 del modulo: dan la textura de "curvas de
    # nivel" sin bordes duros que aliaseen al reducir
    a = np.log(m + 1e-9) / np.log(1.6)          # base chica: mas bandas visibles
    band = 0.5 + 0.5 * np.cos(2 * np.pi * (a - np.floor(a)))
    soft = np.clip(m / 0.22, 0.0, 1.0)          # 0 justo sobre un cero
    shade = 0.34 + 0.66 * band
    shade = shade * soft + (1.0 - soft)         # cerca del cero, sin bandas
    # la saturacion se mantiene alta: sobre el cero el arcoiris da la vuelta
    # entera y eso es justamente lo que hay que ver
    sat = 0.93 * (0.62 + 0.38 * soft)
    # la franja critica manda: el resto del plano se apaga un poco
    focus = 0.60 + 0.40 * np.exp(-((sig[None, :] - 0.5) / 0.85) ** 2)
    val = np.clip(0.40 * shade * focus, 0.0, 1.0)
    rgb = hsv_to_rgb(np.stack([hue, sat, val], axis=-1))
    glow = 1.0 / (1.0 + (m / 0.22) ** 2) ** 1.6
    rgb += (glow * focus)[..., None] * np.array([0.80, 0.94, 1.0]) * 0.55
    return np.clip(rgb, 0.0, 1.0)


def main():
    sig = np.linspace(SIG0, SIG1, W)
    print(f"[zeta] ventana Re(s) [{SIG0}, {SIG1}]  t [{TMIN:.3f}, {TMAX:.3f}]  "
          f"imagen alta {TALL}x{W}")

    for t0 in ZEROS[:3]:
        v = abs(zeta_grid(np.array([0.5]), np.array([t0]))[0, 0])
        assert v < 1e-6, f"zeta(1/2+{t0}i) = {v:.2e}, la evaluacion esta mal"
    print(f"[zeta] chequeo: |zeta(1/2+14.1347i)| = "
          f"{abs(zeta_grid(np.array([0.5]), np.array([ZEROS[0]]))[0, 0]):.2e}")

    # Una sola imagen alta; los frames son recortes.  La fila j corresponde a
    # t = TMAX - j/PPU (t crece hacia arriba, como en el plano complejo).
    tall = np.empty((TALL, W, 3), dtype=np.uint8)
    half = np.empty(TALL, dtype=np.float64)     # |zeta(1/2 + i t)| por fila
    sig_half = np.array([0.5])
    CH = 1024
    for j0 in range(0, TALL, CH):
        j1 = min(TALL, j0 + CH)
        t = TMAX - np.arange(j0, j1) / PPU
        z = zeta_grid(sig, t)
        tall[j0:j1] = (colorize(z, sig) * 255).astype(np.uint8)
        half[j0:j1] = np.abs(zeta_grid(sig_half, t))[:, 0]
        print(f"[zeta] campo {j1}/{TALL}")

    # La recta critica tiene que leerse en un telefono: nucleo duro de unos
    # pocos pixeles mas un halo gaussiano ancho, y brilla donde |zeta| cae.
    xc = int(round((0.5 - SIG0) * PPU))
    lw = max(1, int(round(0.0022 * W)))
    xs = np.arange(W)
    prof = np.exp(-((xs - xc) / (0.020 * W)) ** 2).astype(np.float32)
    prof[xc - lw:xc + lw + 1] = 1.0
    gold = np.array([1.0, 0.80, 0.34], dtype=np.float32)
    line = (0.22 + 0.78 / (1.0 + 2.5 * half)).astype(np.float32)
    # bordes de la franja critica, Re(s) = 0 y Re(s) = 1, apenas insinuados
    edge = np.zeros(W, dtype=np.float32)
    for sv in (0.0, 1.0):
        xe = int(round((sv - SIG0) * PPU))
        if 0 <= xe < W:
            edge[xe] = 1.0
    edge_col = np.array([0.55, 0.75, 1.0], dtype=np.float32) * 0.16

    # El destello es un halo, no un tapon: el nucleo se mantiene chico para no
    # borrar el molinete de fase, y el radio del parche llega a 3.4 sigma para
    # que el borde valga ~0 y no se vea la caja.
    rr = int(round(0.35 * W))
    yy, xx = np.mgrid[-rr:rr + 1, -rr:rr + 1]
    d2 = (yy ** 2 + xx ** 2).astype(np.float32)
    s1, s2 = 0.021 * W, 0.105 * W
    burst = (0.55 * np.exp(-d2 / (2 * s1 ** 2))[..., None] * np.array([0.85, 0.97, 1.0])
             + 0.30 * np.exp(-d2 / (2 * s2 ** 2))[..., None] * np.array([1.0, 0.84, 0.42]))
    burst *= np.clip(1.0 - np.sqrt(d2) / rr, 0.0, 1.0)[..., None] ** 2

    scale_note = ["C2", "G2", "C3", "Eb3", "G3", "Bb3", "C4", "Eb4", "G4", "Bb4"]
    events, zero_hits = [], []
    for i, tz in enumerate(ZEROS):
        f = int(round((tz - C0) / RATE))
        if 0 <= f < FRAMES:
            zero_hits.append({"frame": f, "t": tz, "index": i + 1})
            events.append({"frame": f, "note": scale_note[i % len(scale_note)],
                           "intensity": 0.92})
    print(f"[zeta] {len(zero_hits)} ceros cruzan el centro: "
          + ", ".join(f"{z['t']:.3f}@{z['frame']}" for z in zero_hits))

    for f in range(FRAMES):
        tb = TB0 + RATE * f
        j0 = int(round((TMAX - (tb + TWIN)) * PPU))
        j0 = max(0, min(TALL - H, j0))
        img = tall[j0:j0 + H].astype(np.float32) / 255.0

        col = line[j0:j0 + H]
        img += (col[:, None] * prof[None, :])[..., None] * gold[None, None, :] * 0.62
        img += edge[None, :, None] * edge_col[None, None, :]

        for z in zero_hits:
            y = int(round((TMAX - z["t"]) * PPU)) - j0
            if not (-rr < y < H + rr):
                continue
            amp = float(np.exp(-((y - H / 2) / (0.17 * H)) ** 2))
            ya, yb = max(0, y - rr), min(H, y + rr + 1)
            xa, xb = max(0, xc - rr), min(W, xc + rr + 1)
            img[ya:yb, xa:xb] += (burst[ya - (y - rr):yb - (y - rr),
                                        xa - (xc - rr):xb - (xc - rr)] * amp)

        img = np.clip(img, 0.0, 1.2)
        img = np.clip(img + 0.30 * gaussian_filter(img, (1.9, 1.9, 0)), 0.0, 1.0)
        from PIL import Image
        Image.fromarray((img * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[zeta] {f + 1}/{FRAMES}  t centro = {tb + TWIN / 2:.3f}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "zeros": zero_hits}, jf)
    print(f"[zeta] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
