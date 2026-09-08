"""Buddhabrot — la figura escondida dentro del conjunto de Mandelbrot.

El Mandelbrot clasico pinta CUALES puntos escapan. El Buddhabrot pinta POR
DONDE PASAN los que escapan: se itera z -> z^2 + c, y si la orbita escapa se
suma un conteo en cada casilla que visito en el camino. Los que no escapan se
descartan enteros. Lo que queda es una densidad de probabilidad, no un mapa de
pertenencia, y de ahi que se vea como humo y no como un borde.

El color son tres capas con distinto techo de iteraciones (50, 500 y 5000) en
los canales rojo, verde y azul: las orbitas cortas llenan el cuerpo y las largas
dibujan los filamentos, asi que el canal azul es el que trae el detalle fino.

Va rotado 90 grados, que es la orientacion tradicional y ademas la que hace que
la figura entre en un cuadro vertical.

    python scenes/buddhabrot.py -- --frames 900 --res 1920 --name shorts_buddhabrot --format 9:16
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
NAME = arg("--name", "shorts_buddhabrot")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
SEED = int(arg("--seed", 314159))
BATCH = int(arg("--batch", 10_000))     # candidatos c por frame
# Techos de iteracion por canal. Las orbitas largas dibujan los filamentos y
# las cortas llenan el cuerpo: 5000 al rojo y 50 al azul da el contraste
# clasico de filamentos calidos sobre cuerpo frio.
TIERS = ((5000, 0), (500, 1), (50, 2))
PCT = float(arg("--pct", 99.95))        # percentil de normalizacion
POWER = float(arg("--power", 2.3))      # compresion de los conteos bajos
FADE = int(arg("--fade", 120))          # frames de entrada desde negro

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

# La figura se dibuja acostada y se rota al guardar: alto = eje real.
RE0, RE1 = -1.90, 0.75          # -> altura del cuadro
IM0, IM1 = -0.745, 0.745        # -> ancho del cuadro
GH, GW = H, W                   # histograma ya en la orientacion final

BG = np.array([8, 10, 26], dtype=np.float64)


def in_cardioid_or_bulb(c):
    """Descarta de entrada el cardioide y el bulbo: nunca escapan y son la
    mayor parte del area muestreada. Sin esto se gasta el grueso del tiempo
    iterando 5000 veces puntos que ya se sabe que no sirven."""
    x, y = c.real, c.imag
    q = (x - 0.25) ** 2 + y * y
    card = q * (q + (x - 0.25)) <= 0.25 * y * y
    bulb = (x + 1.0) ** 2 + y * y <= 0.0625
    return card | bulb


def accumulate(rng, hists):
    """Un lote: sortea c, queda con los que escapan y suma sus orbitas."""
    n = BATCH
    cr = rng.uniform(RE0 - 0.35, RE1 + 0.35, n)
    ci = rng.uniform(0.0, IM1 + 0.35, n)        # solo mitad: se refleja despues
    c = cr + 1j * ci
    c = c[~in_cardioid_or_bulb(c)]
    if not len(c):
        return

    for (tier, ch) in TIERS:
        hist = hists[ch]
        # Primera pasada: solo saber quien escapa, sin registrar nada.
        z = np.zeros_like(c)
        alive = np.ones(len(c), dtype=bool)
        esc = np.zeros(len(c), dtype=bool)
        for _ in range(tier):
            z[alive] = z[alive] * z[alive] + c[alive]
            out = alive & (z.real * z.real + z.imag * z.imag > 4.0)
            esc |= out
            alive &= ~out
            if not alive.any():
                break
        ce = c[esc]
        if not len(ce):
            continue

        # Segunda pasada: re-iterar SOLO las que escapan, y ahi si registrar.
        # Los indices se juntan y se vuelcan de a lotes con bincount: np.add.at
        # es un orden de magnitud mas lento y aca se llama miles de veces.
        z = np.zeros_like(ce)
        live = np.ones(len(ce), dtype=bool)
        pend, npend = [], 0
        flat = hist.reshape(-1)
        for _ in range(tier):
            z[live] = z[live] * z[live] + ce[live]
            live &= (z.real * z.real + z.imag * z.imag) <= 4.0
            if not live.any():
                break
            zr, zi = z.real[live], z.imag[live]
            row = ((zr - RE0) / (RE1 - RE0) * GH).astype(np.int64)
            # el eje real es simetrico: cada punto cuenta tambien reflejado
            for sign in (1.0, -1.0):
                col = ((sign * zi - IM0) / (IM1 - IM0) * GW).astype(np.int64)
                ok = (row >= 0) & (row < GH) & (col >= 0) & (col < GW)
                if ok.any():
                    pend.append(row[ok] * GW + col[ok])
                    npend += int(ok.sum())
            if npend > 3_000_000:
                flat += np.bincount(np.concatenate(pend), minlength=GH * GW).astype(np.int32)
                pend, npend = [], 0
        if pend:
            flat += np.bincount(np.concatenate(pend), minlength=GH * GW).astype(np.int32)


def render(hists, fade=1.0):
    """Normaliza por percentil alto y comprime los conteos bajos con una
    potencia > 1.

    Casi todo el cuadro tiene conteo bajo pero no nulo: las orbitas cortas pasan
    por todas partes. Con una curva que levante esos valores (gamma < 1) la
    figura se lava en un fondo celeste; hay que hundirlos, no realzarlos.
    """
    img = np.zeros((GH, GW, 3), dtype=np.float64)
    for ch in range(3):
        h = gaussian_filter(hists[ch].astype(np.float64), 0.7)
        nz = h[h > 0]
        m = np.percentile(nz, PCT) if nz.size else 1.0
        img[:, :, ch] = np.clip(h / max(m, 1e-9), 0, 1) ** POWER
    out = BG + (255.0 - BG) * img * fade
    return np.clip(out, 0, 255).astype(np.uint8)


def main():
    rng = np.random.default_rng(SEED)
    hists = [np.zeros((GH, GW), dtype=np.int32) for _ in TIERS]
    print(f"[buddha] {FRAMES} frames | {W}x{H} | lote {BATCH:,} | techos {TIERS}")
    scale_note = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3"]
    events = []

    dump = arg("--dump")
    for f in range(FRAMES):
        accumulate(rng, hists)
        # sin el fundido, el primer segundo es un campo de ruido normalizado
        Image.fromarray(render(hists, min(1.0, (f + 1) / FADE) ** 0.6), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))
        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 50 == 0 or f == FRAMES - 1:
            tot = sum(int(h.sum()) for h in hists)
            print(f"[buddha] {f + 1}/{FRAMES}  puntos acumulados {tot:,}")
    if dump:
        np.save(dump, np.stack(hists))
        print(f"[buddha] histogramas -> {dump}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[buddha] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
