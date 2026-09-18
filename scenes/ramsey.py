"""R(3,3) = 6: en cualquier grupo de seis, tres se conocen o tres no.

Se pintan las aristas del grafo completo de dos colores. Un triangulo
monocromatico son tres nodos con sus tres aristas del mismo color: tres que se
conocen entre si, o tres que no se conocen entre si.

Con CINCO nodos se puede evitar. Hay 2^10 = 1024 coloreos de K5 y 12 de ellos
no tienen ni un triangulo monocromatico (el pentagono contra el pentagrama).

Con SEIS ya no. Hay 2^15 = 32768 coloreos de K6 y en NINGUNO se puede evitar.
Y no aparece uno: el minimo sobre los 32768 es DOS. El promedio es 5.

Todo eso esta enumerado de verdad al arrancar la escena, no citado: se
recorren los 1024 y los 32768 coloreos y se cuentan los triangulos de cada
uno. Si alguna vez apareciera un escape en K6, la escena aborta.

No hay ecuacion aca. Es un argumento de conteo: de las cinco aristas que salen
de un nodo, tres son del mismo color por palomar; si dos de esos tres vecinos
estan unidos por ese color, ya hay triangulo, y si no, los tres forman uno del
otro color. Ese es todo el teorema.

    python scenes/ramsey.py -- --frames 900 --res 1920 --name shorts_ramsey --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import math
import os
import sys
from itertools import combinations

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_ramsey")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
SS = int(arg("--ss", 2))
SEED = int(arg("--seed", 5))

F_K5_END = int(arg("--f5", 250))        # hasta aca se ve K5
F_GROW = int(arg("--fgrow", 320))       # entra el sexto nodo
F_HOLD = int(arg("--fhold", 845))       # remate final

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

COL = (np.array([1.00, 0.42, 0.30]), np.array([0.32, 0.76, 1.00]))   # calido, frio
BG = (6, 8, 20)

rng = np.random.default_rng(SEED)


def graph_parts(n):
    edges = list(combinations(range(n), 2))
    eidx = {e: i for i, e in enumerate(edges)}
    tris = [(a, b, c, eidx[(a, b)], eidx[(a, c)], eidx[(b, c)])
            for a, b, c in combinations(range(n), 3)]
    return edges, tris


def mono(mask, tris):
    out = []
    for (a, b, c, i, j, k) in tris:
        bi, bj, bk = (mask >> i) & 1, (mask >> j) & 1, (mask >> k) & 1
        if bi == bj == bk:
            out.append((a, b, c, bi))
    return out


def enumerate_all(n):
    edges, tris = graph_parts(n)
    counts = np.empty(1 << len(edges), dtype=np.int16)
    free = []
    for mask in range(1 << len(edges)):
        c = len(mono(mask, tris))
        counts[mask] = c
        if c == 0:
            free.append(mask)
    return edges, tris, counts, free


def main():
    e5, t5, c5, free5 = enumerate_all(5)
    e6, t6, c6, free6 = enumerate_all(6)
    assert len(free6) == 0, f"K6 tendria {len(free6)} escapes; el teorema falla"
    assert c6.min() == 2, f"el minimo en K6 dio {c6.min()}, no 2"
    print(f"[ramsey] K5: {1 << len(e5)} coloreos, {len(free5)} sin triangulo "
          f"monocromatico, minimo {c5.min()}, promedio {c5.mean():.2f}")
    print(f"[ramsey] K6: {1 << len(e6)} coloreos, {len(free6)} sin triangulo "
          f"monocromatico, minimo {c6.min()}, promedio {c6.mean():.2f}")

    # --- guion de coloreos -------------------------------------------------
    # K5: unos cuantos al azar (con triangulos) y despues uno de los 12 que
    # escapan, sostenido: ahi se ve que con cinco SI se puede.
    seq5 = [int(rng.integers(1 << len(e5))) for _ in range(5)] + [int(free5[0])]
    # K6: caminata por el espacio de coloreos cambiando UNA arista por paso,
    # que es a la vez la animacion natural y un recorrido legitimo.
    m = int(rng.integers(1 << len(e6)))
    seq6 = [m]
    for _ in range(400):
        m ^= 1 << int(rng.integers(len(e6)))
        seq6.append(m)

    def frame_state(f):
        """(n, mascara, indice de coloreo dentro de su fase)."""
        if f < F_K5_END:
            i = min(len(seq5) - 1, int(f / (F_K5_END / len(seq5))))
            return 5, seq5[i], i
        if f < F_GROW:
            return 6, seq5[-1] | (int(seq6[0]) & ~((1 << len(e5)) - 1)), 0
        # el ritmo se acelera: arranca en 14 frames por coloreo y baja a 3
        g = (min(f, F_HOLD) - F_GROW) / max(1, F_HOLD - F_GROW)
        step = 14 - 11 * g
        i = 0
        acc, ff = 0.0, F_GROW
        while ff < min(f, F_HOLD):
            gg = (ff - F_GROW) / max(1, F_HOLD - F_GROW)
            acc += 1.0 / (14 - 11 * gg)
            ff += 1
        i = int(acc)
        return 6, seq6[min(i, len(seq6) - 1)], i

    # bar strip: un registro por coloreo mostrado
    bars = []          # (n, cuantos triangulos monocromaticos)
    last_key = None

    fp = font_path("bold")
    fnt = ImageFont.truetype(fp, int(0.030 * W)) if fp else ImageFont.load_default()
    fnt_s = ImageFont.truetype(fp, int(0.021 * W)) if fp else ImageFont.load_default()

    cxg, cyg = W / 2.0, 0.470 * H
    Rg = 0.330 * W
    sy0, sy1 = int(0.690 * H), int(0.762 * H)

    scale_note = ["E3", "G3", "B3", "D4", "E4", "G4", "B4", "D5"]
    events = []

    for f in range(FRAMES):
        n, mask, idx = frame_state(f)
        edges = e6 if n == 6 else e5
        tris = t6 if n == 6 else t5
        tm = mono(mask, tris)

        key = (n, mask)
        if key != last_key:
            bars.append((n, len(tm)))
            last_key = key

        img = Image.new("RGB", (W * SS, H * SS), BG)
        dr = ImageDraw.Draw(img, "RGBA")

        rot = 0.20 * f / FPS
        # el sexto nodo entra creciendo entre F_K5_END y F_GROW
        grow = np.clip((f - F_K5_END) / max(1, F_GROW - F_K5_END), 0.0, 1.0)
        nn = 6 if f >= F_K5_END else 5
        base = 6 if f >= F_K5_END else 5
        pos = []
        for v in range(nn):
            ang = rot - math.pi / 2 + 2 * math.pi * v / base
            pos.append((cxg + Rg * math.cos(ang), cyg + Rg * math.sin(ang)))

        # caras de los triangulos monocromaticos
        for (a, b, c, col) in tm:
            if max(a, b, c) >= nn:
                continue
            rgb = COL[col]
            # alfa bajo a proposito: con cinco o seis triangulos encima,
            # un relleno fuerte se vuelve una mancha marron sin forma
            fill = tuple(int(255 * x) for x in rgb) + (46,)
            dr.polygon([(pos[a][0] * SS, pos[a][1] * SS),
                        (pos[b][0] * SS, pos[b][1] * SS),
                        (pos[c][0] * SS, pos[c][1] * SS)], fill=fill)

        for i, (a, b) in enumerate(edges):
            if max(a, b) >= nn:
                continue
            col = COL[(mask >> i) & 1]
            al = 255 if (a < 5 and b < 5) else int(255 * grow)
            c = tuple(int(255 * x) for x in col) + (al,)
            dr.line([(pos[a][0] * SS, pos[a][1] * SS),
                     (pos[b][0] * SS, pos[b][1] * SS)],
                    fill=c, width=max(SS, int(0.0062 * W * SS)))

        for v in range(nn):
            r = 0.0235 * W * SS * (grow if v == 5 else 1.0)
            if r <= 0:
                continue
            dr.ellipse([pos[v][0] * SS - r, pos[v][1] * SS - r,
                        pos[v][0] * SS + r, pos[v][1] * SS + r],
                       fill=(238, 242, 252), outline=(120, 132, 168), width=SS)

        # tira de barras: una por coloreo mostrado, altura = triangulos
        sw = int(0.86 * W)
        sx = (W - sw) // 2
        dr.rectangle([sx * SS, sy0 * SS, (sx + sw) * SS, sy1 * SS],
                     outline=(48, 56, 84), width=SS)
        dr.line([(sx * SS, (sy1 - 1) * SS), ((sx + sw) * SS, (sy1 - 1) * SS)],
                fill=(120, 90, 90), width=SS)
        nb = max(1, len(bars))
        bw = sw / max(60, nb)
        for bi, (bn, bc) in enumerate(bars):
            x = sx + bi * bw
            hgt = (sy1 - sy0 - 4) * min(1.0, bc / 12.0)
            cc = (120, 210, 150) if bc == 0 else ((250, 140, 110) if bn == 6
                                                  else (150, 165, 205))
            if bc == 0:
                dr.line([(x * SS, (sy1 - 3) * SS), ((x + bw) * SS, (sy1 - 3) * SS)],
                        fill=cc, width=3 * SS)
            else:
                dr.rectangle([x * SS, (sy1 - 2 - hgt) * SS,
                              (x + max(bw - 0.6, 0.8)) * SS, (sy1 - 2) * SS], fill=cc)

        lab = f"K{nn}   monochromatic triangles: {len(tm)}"
        dr.text((cxg * SS, 0.146 * H * SS), lab, font=fnt,
                fill=(230, 236, 250), anchor="mm")
        tried5 = sum(1 for b in bars if b[0] == 5)
        tried6 = sum(1 for b in bars if b[0] == 6)
        sub = (f"colourings shown   K5: {tried5}    K6: {tried6}"
               f"    escapes: {sum(1 for b in bars if b[1] == 0)}")
        dr.text((cxg * SS, 0.784 * H * SS), sub, font=fnt_s,
                fill=(160, 175, 210), anchor="mm")

        a = np.asarray(img.resize((W, H), Image.LANCZOS)).astype(np.float32) / 255.0
        a = np.clip(a + 0.52 * gaussian_filter(a, (2.0, 2.0, 0)), 0.0, 1.0)
        Image.fromarray((a * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[ramsey] {f + 1}/{FRAMES}  K{nn}  triangulos {len(tm)}  "
                  f"coloreos mostrados {len(bars)}")

    zero6 = sum(1 for b in bars if b[0] == 6 and b[1] == 0)
    print(f"[ramsey] mostrados {len(bars)} coloreos; escapes en K6: {zero6}")
    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "k5_total": 1 << len(e5), "k5_free": len(free5),
                   "k6_total": 1 << len(e6), "k6_free": len(free6),
                   "k6_min": int(c6.min()), "k6_mean": float(c6.mean()),
                   "shown": len(bars), "shown_zero_k6": zero6,
                   "f_grow": F_GROW, "bars": bars}, jf)
    print(f"[ramsey] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
