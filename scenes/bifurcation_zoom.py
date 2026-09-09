"""Diagrama de bifurcacion del mapa logistico, con zoom al punto de Feigenbaum.

Se itera x -> r*x*(1-x) para cada r, se descarta el transitorio y se grafica el
atractor: un punto fijo, luego 2, luego 4, 8, 16... y despues caos. Las
bifurcaciones se acumulan hacia r_inf = 3.5699456718..., y las distancias entre
una y la siguiente tienden a una razon fija:

    delta = 4.6692016091...  (horizontal, en r)
    alpha = 2.5029078750...  (vertical, en x)

Esas dos constantes son de Feigenbaum y son UNIVERSALES: valen para cualquier
mapa unimodal con maximo cuadratico, no solo para este. De ahi que aparezcan en
sistemas fisicos que no tienen nada que ver entre si.

El zoom usa esas dos razones: la ventana se encoge por delta en r y por alpha en
x, que es el ritmo al que la cascada se acumula. Arranca en la vista ancha
reconocible y baja unas 5,5 duplicaciones, o sea unas 6700 veces en r.

NO cierra en loop, y la version anterior de este archivo suponia que si. La
autosemejanza de Feigenbaum vale para la estructura LOCAL de la cascada, no
reproduce el cuadro entero a escala: medido, la correlacion entre el primer
frame y el que cerraria el ciclo da 0,14, o sea nada.

El eje r va en VERTICAL, que es lo que hace entrar el arbol en un cuadro 9:16.

    python scenes/bifurcation_zoom.py -- --frames 900 --res 1920 --name shorts_feigenbaum --format 9:16
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
NAME = arg("--name", "shorts_feigenbaum")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
TRANSIENT = int(arg("--transient", 2600))   # iteraciones descartadas
RECORD = int(arg("--record", 3000))         # iteraciones graficadas
SS = int(arg("--ss", 2))                    # supermuestreo del eje r
DOUBLINGS = float(arg("--doublings", 5.5))  # duplicaciones recorridas
START = float(arg("--start", 0.0))          # 0 = vista ancha reconocible
EXPOSURE = float(arg("--exposure", 2.6))
GLOW = float(arg("--glow", 0.45))
PCT = float(arg("--pct", 97.0))            # percentil de normalizacion

DELTA = 4.6692016091029907       # Feigenbaum, horizontal (en r)
ALPHA = 2.5029078750958928       # Feigenbaum, vertical (en x)
R_INF = 3.5699456718709449       # punto de acumulacion de la cascada
X_C = 0.5                        # punto critico del mapa
# Ventana asimetrica en r: por debajo llega hasta 2.95 (la primera
# bifurcacion, en r=3) y por arriba corta en 4.00, donde el mapa se escapa.
RW_LO = 0.62
RW_HI = 0.43
X_W0 = 0.46                      # media ventana inicial en x

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
COOL = np.array([0.30, 0.90, 1.00])      # poca densidad: cian
WARM = np.array([1.00, 0.82, 0.34])      # mucha densidad: oro


def frame_histogram(s):
    """Histograma del atractor en la ventana correspondiente a s duplicaciones."""
    k = DELTA ** (-s)
    xw = X_W0 * ALPHA ** (-s)
    r0, r1 = R_INF - RW_LO * k, R_INF + RW_HI * k
    x0, x1 = X_C - xw, X_C + xw

    nr = H * SS
    # una fila del cuadro = un valor de r; el eje r va vertical
    r = np.linspace(r0, r1, nr)
    x = np.full(nr, 0.5000001)
    for _ in range(TRANSIENT):
        x = r * x * (1.0 - x)

    hist = np.zeros(H * W, dtype=np.int32)
    rows = (np.arange(nr) // SS).astype(np.int64)
    pend, npend = [], 0
    for _ in range(RECORD):
        x = r * x * (1.0 - x)
        col = ((x - x0) / (x1 - x0) * W).astype(np.int64)
        ok = (col >= 0) & (col < W)
        if ok.any():
            pend.append(rows[ok] * W + col[ok])
            npend += int(ok.sum())
        if npend > 2_000_000:
            hist += np.bincount(np.concatenate(pend), minlength=H * W).astype(np.int32)
            pend, npend = [], 0
    if pend:
        hist += np.bincount(np.concatenate(pend), minlength=H * W).astype(np.int32)
    return hist.reshape(H, W)


def render(hist):
    # float32 y percentil sobre una submuestra: el revelado era 8 veces mas
    # caro que el calculo del atractor, y el filtro gaussiano se lleva todo.
    h = gaussian_filter(hist.astype(np.float32), 0.7)
    nz = h[h > 0]
    m = float(np.percentile(nz[::7], PCT)) if nz.size else 1.0
    m = max(m, 1e-9)
    v = 1.0 - np.exp(-EXPOSURE * h / m, dtype=np.float32)
    v = np.clip(v + GLOW * gaussian_filter(v, 2.6), 0.0, 1.0)
    # el color codifica densidad: donde el atractor se demora, se pone oro
    d = np.clip(h / m, 0.0, 1.0)[:, :, None]
    col = COOL[None, None, :] * (1 - d) + WARM[None, None, :] * d
    img = BG + (255.0 - BG) * (v[:, :, None] * col)
    return np.clip(img, 0, 255).astype(np.uint8)


def main():
    print(f"[feigen] {FRAMES} frames | {W}x{H} (ss{SS}) | {DOUBLINGS} duplicaciones/ciclo")
    scale_note = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3"]
    events = []
    for f in range(FRAMES):
        s = START + DOUBLINGS * f / FRAMES
        Image.fromarray(render(frame_histogram(s)), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))
        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 50 == 0 or f == FRAMES - 1:
            print(f"[feigen] {f + 1}/{FRAMES}  s={s:.3f}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[feigen] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
