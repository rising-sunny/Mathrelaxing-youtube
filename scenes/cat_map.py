"""Mapa del gato de Arnold: destruir una imagen y que vuelva exacta.

La regla es una sola linea. A cada pixel (x, y) de una imagen de N x N:

    (x, y)  ->  (2x + y,  x + y)   mod N

Nada mas. El determinante de esa matriz es 1, asi que no se crea ni se pierde
un solo pixel: es una PERMUTACION de la imagen. Y sus autovalores son
(3 +- sqrt 5)/2, o sea phi^2 = 2.618 y su inverso: cada paso estira por phi^2
en una direccion y comprime por lo mismo en la otra. En diez pasos la imagen
es ruido.

Lo que no se espera: como es una permutacion de un conjunto finito, tiene
orden finito. Repitiendola lo suficiente la imagen vuelve. No parecida:
IDENTICA, pixel por pixel. Para N = 533 el orden es 140, verificado iterando
la permutacion entera y comparando contra la original.

El periodo depende de N de una forma erratica y sin formula cerrada conocida:
N = 533 da 140, pero N = 127 da 128 y N = 124 da 15.

Al ser una permutacion, el histograma se conserva exacto: el brillo medio del
cuadro es el mismo en todos los frames. Por eso los cortes rapidos entre pasos
no producen destellos, aunque el dibujo cambie mucho.

    python scenes/cat_map.py -- --frames 900 --res 1920 --name shorts_catmap --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_catmap")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
N = int(arg("--n", 533))                # lado del toro; su orden es 140
STEP_FRAMES = int(arg("--step-frames", 5))
FADE = float(arg("--fade", 0.40))       # fraccion del paso que dura el cruce
# Un segundo de imagen intacta al arranque: sin esto el primer frame ya sale
# desarmado y el que cae ahi no sabe QUE se esta destruyendo, que es medio
# short perdido.
HOLD_START = int(arg("--hold-start", 60))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from paths import font_path  # noqa: E402

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


def source_image():
    """Un pi grande sobre un fondo de color lleno.

    Tiene que leerse de un vistazo (para que el regreso sea obvio) y a la vez
    tener color en TODO el cuadro: con fondo oscuro, la imagen desarmada queda
    en un ruido apagado y no se ve nada. Aca el fondo es un degradado vivo, y
    el ruido del medio del clip hereda esa paleta.

    Se dibuja a 4x y se baja, que es la unica forma de que el glifo no quede
    dentado a 533 px.
    """
    S = N * 4
    yy, xx = np.mgrid[0:S, 0:S]
    u = xx / (S - 1.0)
    v = yy / (S - 1.0)
    # degradado diagonal azul profundo -> turquesa -> violeta
    base = np.stack([0.10 + 0.22 * u + 0.30 * v * v,
                     0.16 + 0.52 * (1 - v) * (0.35 + 0.65 * u),
                     0.34 + 0.46 * v + 0.18 * (1 - u)], axis=-1)
    # anillos concentricos: la textura fina que hace visible el estiramiento
    r = np.sqrt((u - 0.5) ** 2 + (v - 0.5) ** 2)
    base *= (0.86 + 0.14 * np.cos(r * 150.0))[..., None]
    img = Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8))

    fp = font_path("bold")
    fnt = ImageFont.truetype(fp, int(S * 0.78)) if fp else ImageFont.load_default()
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).text((S / 2, S / 2), "\u03c0", font=fnt, fill=255, anchor="mm")
    glyph = np.stack([np.full((S, S), 1.00) - 0.10 * v,
                      np.full((S, S), 0.86) - 0.42 * v,
                      np.full((S, S), 0.34) + 0.30 * v], axis=-1)
    a = np.asarray(img).astype(np.float32) / 255.0
    m = (np.asarray(mask).astype(np.float32) / 255.0)[..., None]
    a = a * (1 - m) + glyph.astype(np.float32) * m
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return np.asarray(out.resize((N, N), Image.LANCZOS)).astype(np.float32) / 255.0


def main():
    src = source_image()
    yy, xx = np.mgrid[0:N, 0:N]
    dest = (((xx + yy) % N) * N + ((2 * xx + yy) % N)).ravel()   # a donde va cada pixel

    # Orden de la permutacion, medido y no supuesto.
    probe = np.arange(N * N)
    cur = probe.copy()
    period = None
    for k in range(1, 4000):
        nxt = np.empty_like(cur)
        nxt[dest] = cur
        cur = nxt
        if np.array_equal(cur, probe):
            period = k
            break
    if period is None:
        sys.exit(f"El mapa no cerro para N={N}")
    lam = (3 + math.sqrt(5)) / 2
    print(f"[cat] N={N}  orden de la permutacion = {period}  "
          f"autovalor {lam:.6f} = phi^2")

    total_steps = period
    span = total_steps * STEP_FRAMES
    ret = HOLD_START + span                       # frame en que vuelve exacta
    if ret > FRAMES:
        sys.exit(f"No entran {HOLD_START} + {total_steps}x{STEP_FRAMES} en {FRAMES}")
    print(f"[cat] {HOLD_START} frames intacta + {total_steps} pasos x "
          f"{STEP_FRAMES} = vuelve en el frame {ret}, y {FRAMES - ret} de premio")

    # Los 141 estados se guardan en uint8: en float32 son 480 MB para nada,
    # porque la permutacion no cambia los valores, solo los reordena.
    u8 = (np.clip(src, 0, 1) * 255).astype(np.uint8)
    states = [u8]
    flat = u8.reshape(-1, 3)
    for _ in range(total_steps):
        nxt = np.empty_like(flat)
        nxt[dest] = flat
        flat = nxt
        states.append(flat.reshape(N, N, 3))
    back = int(np.abs(states[-1].astype(np.int16) - u8.astype(np.int16)).max())
    print(f"[cat] diferencia entre el paso {total_steps} y el original: {back} niveles")

    up = max(1, (W - 8) // N)
    side = N * up
    x0 = (W - side) // 2
    y0 = (H - side) // 2
    print(f"[cat] cuadro {W}x{H}, imagen {side}x{side} (x{up}) en ({x0},{y0})")

    scale_note = ["A2", "C3", "E3", "A3", "C4", "E4", "A4", "C5"]
    events = []

    for f in range(FRAMES):
        if f < HOLD_START:
            a = states[0].astype(np.float32) / 255.0
            step_shown = 0
        elif f < ret:
            k, r = divmod(f - HOLD_START, STEP_FRAMES)
            # el estado se mantiene limpio y recien al final cruza al siguiente
            u = max(0.0, (r / STEP_FRAMES - (1 - FADE)) / FADE)
            u = u * u * (3 - 2 * u)
            a = (states[k].astype(np.float32) * (1 - u)
                 + states[k + 1].astype(np.float32) * u) / 255.0 if u > 0 \
                else states[k].astype(np.float32) / 255.0
            step_shown = k
        else:
            a = states[total_steps].astype(np.float32) / 255.0
            step_shown = total_steps

        tile = np.repeat(np.repeat(a, up, axis=0), up, axis=1)
        img = np.zeros((H, W, 3), dtype=np.float32)
        img[y0:y0 + side, x0:x0 + side] = tile

        # un fogonazo corto justo cuando la imagen vuelve
        if ret <= f < ret + 26:
            img = np.clip(img * (1.0 + 0.85 * math.exp(-(f - ret) / 7.0)), 0, 1)

        img = np.clip(img + 0.30 * gaussian_filter(img, (1.5, 1.5, 0)), 0.0, 1.0)
        Image.fromarray((img * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[cat] {f + 1}/{FRAMES}  paso {step_shown}/{total_steps}")

    events.append({"frame": ret, "note": "A4", "intensity": 1.0})
    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "n": N, "period": total_steps, "step_frames": STEP_FRAMES,
                   "return_frame": ret, "hold_start": HOLD_START, "max_diff": int(back)}, jf)
    print(f"[cat] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
