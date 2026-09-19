"""Los 17 grupos de papel tapiz.

Un patron que se repite en el plano puede tener muchas simetrias: traslaciones,
giros, espejos, deslizamientos. La pregunta es cuantas combinaciones distintas
son posibles, y la respuesta es exactamente 17. Ni 16 ni 18. Fedorov lo probo
en 1891.

Cada grupo se construye aca cerrando sus generadores como isometrias afines
(M, t) en coordenadas de red, modulo Z^2, y se comprueba:
  - que el grupo cierra y su orden puntual es el de la tabla conocida;
  - que los 17 tienen FIRMAS distintas (red, orden, espejos puros,
    deslizamientos, ordenes de rotacion, y cuantos centros de rotacion caen
    sobre un espejo).

Esa ultima comprobacion no es decorativa: la primera version tenia dos copias
de p31m y ningun p3m1, porque las dos reflexiones hexagonales que elegi eran
conjugadas. Lo que las separa es si los tres centros de orden 3 de la celda
caen sobre espejos (p3m1) o solo uno (p31m).

El dibujo no usa dominio fundamental. Se toma un motivo asimetrico -- unas
gaussianas sueltas -- y se PROMEDIA sobre el grupo:

    F(p) = sum_{g en G} sum_{n en Z^2} f(g.p + n)

Promediar sobre un grupo da una funcion invariante por construccion, sin tener
que recortar nada ni preocuparse por bordes.

Los grupos van ordenados por simetria creciente, de p1 (solo traslaciones) a
p6m (12 simetrias puntuales): el clip es un crescendo, no un catalogo.

    python scenes/wallpaper.py -- --frames 900 --res 1920 --name shorts_wallpaper --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import math
import os
import sys
from fractions import Fraction as Fr

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_wallpaper")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
TILE = int(arg("--tile", 384))
CELLS = float(arg("--cells", 3.1))      # celdas a lo ancho del cuadro
FADE = int(arg("--fade", 14))           # frames de cruce entre grupos
SEED = int(arg("--seed", 19))

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

Z = (Fr(0), Fr(0))
h = Fr(1, 2)
R2 = ((-1, 0), (0, -1)); R4 = ((0, -1), (1, 0))
MX = ((1, 0), (0, -1)); MY = ((-1, 0), (0, 1)); D = ((0, 1), (1, 0))
R3 = ((0, -1), (1, -1)); R6 = ((1, -1), (1, 0))
# Las dos reflexiones hexagonales NO son intercambiables: la primera deja los
# tres centros de orden 3 sobre espejos (p3m1), la segunda solo uno (p31m).
M_P3M1 = ((0, -1), (-1, 0))
M_P31M = ((0, 1), (1, 0))

GROUPS = {
    "p1": ("sq", []), "p2": ("sq", [(R2, Z)]), "pm": ("sq", [(MX, Z)]),
    "pg": ("sq", [(MX, (h, Fr(0)))]), "cm": ("sq", [(D, Z)]),
    "pmm": ("sq", [(MX, Z), (MY, Z)]), "pmg": ("sq", [(R2, Z), (MX, (h, Fr(0)))]),
    "pgg": ("sq", [(R2, Z), (MX, (h, h))]), "cmm": ("sq", [(D, Z), (R2, Z)]),
    "p4": ("sq", [(R4, Z)]), "p4m": ("sq", [(R4, Z), (MX, Z)]),
    "p4g": ("sq", [(R4, Z), (MX, (h, h))]),
    "p3": ("hex", [(R3, Z)]), "p3m1": ("hex", [(R3, Z), (M_P3M1, Z)]),
    "p31m": ("hex", [(R3, Z), (M_P31M, Z)]), "p6": ("hex", [(R6, Z)]),
    "p6m": ("hex", [(R6, Z), (M_P3M1, Z)]),
}
EXPECTED_ORDER = {"p1": 1, "p2": 2, "pm": 2, "pg": 2, "cm": 2, "pmm": 4,
                  "pmg": 4, "pgg": 4, "cmm": 4, "p4": 4, "p4m": 8, "p4g": 8,
                  "p3": 3, "p3m1": 6, "p31m": 6, "p6": 6, "p6m": 12}

B_SQ = np.array([[1.0, 0.0], [0.0, 1.0]])
B_HEX = np.array([[1.0, -0.5], [0.0, math.sqrt(3) / 2]])

PALETTE = np.array([[0.03, 0.05, 0.14], [0.08, 0.26, 0.42], [0.16, 0.55, 0.62],
                    [0.72, 0.52, 0.22], [0.98, 0.84, 0.56]], dtype=np.float32)


def _mul(A, B):
    return tuple(tuple(sum(A[i][k] * B[k][j] for k in range(2)) for j in range(2))
                 for i in range(2))


def _comp(a, b):
    (M1, t1), (M2, t2) = a, b
    return (_mul(M1, M2),
            tuple((sum(M1[i][k] * t2[k] for k in range(2)) + t1[i]) % 1
                  for i in range(2)))


def close_group(gens):
    I = (((1, 0), (0, 1)), Z)
    G = {I}
    frontier = [I]
    while frontier:
        nxt = []
        for g in frontier:
            for gen in gens:
                x = _comp(g, gen)
                if x not in G:
                    G.add(x)
                    nxt.append(x)
        frontier = nxt
        if len(G) > 64:
            raise RuntimeError("el grupo no cierra")
    return sorted(G, key=repr)


def _det(M):
    return M[0][0] * M[1][1] - M[0][1] * M[1][0]


def _rot_order(M):
    I = ((1, 0), (0, 1)); A = M; k = 1
    while A != I:
        A = _mul(A, M); k += 1
    return k


def _has_fixed(g, n=12):
    M, t = g
    for i in range(n):
        for j in range(n):
            p = (Fr(i, n), Fr(j, n))
            q = tuple((sum(M[a][b] * p[b] for b in range(2)) + t[a]) % 1
                      for a in range(2))
            if q == p:
                return True
    return False


def signature(name, lat, G):
    refl = sum(1 for g in G if _det(g[0]) == -1 and _has_fixed(g))
    glide = sum(1 for g in G if _det(g[0]) == -1 and not _has_fixed(g))
    rots = tuple(sorted(_rot_order(g[0]) for g in G if _det(g[0]) == 1))
    centres = ([(Fr(0), Fr(0)), (Fr(1, 3), Fr(2, 3)), (Fr(2, 3), Fr(1, 3))]
               if lat == "hex" else
               [(Fr(0), Fr(0)), (h, h), (h, Fr(0)), (Fr(0), h)])
    rf = [g for g in G if _det(g[0]) == -1]
    on = sum(1 for c in centres
             if any(tuple((sum(g[0][a][b] * c[b] for b in range(2)) + g[1][a]) % 1
                          for a in range(2)) == c for g in rf))
    return (lat, len(G), refl, glide, rots, on)


def build_tile(G, lat, rng):
    """Promedia un motivo asimetrico sobre el grupo: invariante por construccion."""
    B = B_HEX if lat == "hex" else B_SQ
    nb = 4
    q = rng.uniform(0.08, 0.92, (nb, 2))
    wgt = rng.uniform(0.55, 1.0, nb)
    sig = 0.155

    u = (np.arange(TILE) + 0.5) / TILE
    UU, VV = np.meshgrid(u, u, indexing="ij")
    out = np.zeros((TILE, TILE), dtype=np.float32)
    for (M, t) in G:
        # El punto transformado se ENVUELVE a la celda antes de sumar los
        # vecinos. Sin esto, g.p puede caer tres o cuatro celdas afuera y una
        # ventana de 3x3 se queda corta: la funcion deja de ser periodica y el
        # tejido sale con costuras rectas (medido: error 5.9 sobre un rango de
        # 11). Envolviendo, la periodicidad es exacta por construccion y
        # bastan los 9 vecinos.
        mu = (float(M[0][0]) * UU + float(M[0][1]) * VV + float(t[0])) % 1.0
        mv = (float(M[1][0]) * UU + float(M[1][1]) * VV + float(t[1])) % 1.0
        for k in range(nb):
            for nx in (-1, 0, 1):
                for ny in (-1, 0, 1):
                    du = mu + nx - q[k, 0]
                    dv = mv + ny - q[k, 1]
                    x = B[0, 0] * du + B[0, 1] * dv
                    y = B[1, 0] * du + B[1, 1] * dv
                    out += wgt[k] * np.exp(-(x * x + y * y) / (2 * sig * sig))
    # Normalizacion por percentil y no por maximo: los grupos hexagonales
    # suman mas terminos, su F es mas grande y con max() salian lavados en el
    # extremo claro de la paleta mientras los de orden bajo usaban medio rango.
    lo, hi = np.percentile(out, 2.0), np.percentile(out, 98.0)
    return np.clip((out - lo) / max(hi - lo, 1e-9), 0.0, 1.0).astype(np.float32)


def colorize(v):
    n = len(PALETTE) - 1
    x = np.clip(v, 0.0, 1.0) * n
    i = np.clip(x.astype(np.int32), 0, n - 1)
    f = (x - i)[..., None]
    return PALETTE[i] * (1 - f) + PALETTE[i + 1] * f


def main():
    rng = np.random.default_rng(SEED)
    sigs, built = {}, {}
    for name, (lat, gens) in GROUPS.items():
        G = close_group(gens)
        pts = {g[0] for g in G}
        assert len(pts) == EXPECTED_ORDER[name], \
            f"{name}: orden puntual {len(pts)}, esperado {EXPECTED_ORDER[name]}"
        s = signature(name, lat, G)
        assert s not in sigs, f"{name} y {sigs[s]} tienen la misma firma: {s}"
        sigs[s] = name
        built[name] = (lat, G, s)
    print(f"[wp] {len(built)} grupos, todos cerrados, con el orden correcto "
          f"y con firmas distintas")

    order = sorted(built, key=lambda n: (EXPECTED_ORDER[n], n))
    print("[wp] orden de aparicion: " + " -> ".join(order))

    tiles, metas = [], []
    for name in order:
        lat, G, s = built[name]
        tiles.append(build_tile(G, lat, np.random.default_rng(SEED + len(tiles))))
        metas.append({"name": name, "lattice": lat, "order": EXPECTED_ORDER[name],
                      "mirrors": s[2], "glides": s[3]})
        print(f"[wp] tejido {name:5s} orden {EXPECTED_ORDER[name]:2d} "
              f"espejos {s[2]} deslizamientos {s[3]}")

    # El ultimo (p6m, el mas simetrico) se queda mas tiempo: es el remate.
    tail = int(0.145 * FRAMES)
    per = (FRAMES - tail) // (len(order) - 1)
    bounds = [i * per for i in range(len(order))] + [FRAMES]
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    scale = CELLS / W
    Xc = (xs - W / 2) * scale
    Yc = (ys - H / 2) * scale

    Binv = {"sq": np.linalg.inv(B_SQ), "hex": np.linalg.inv(B_HEX)}

    def sample(idx, dx, dy):
        lat = metas[idx]["lattice"]
        Bi = Binv[lat]
        u = Bi[0, 0] * Xc + Bi[0, 1] * Yc + dx
        v = Bi[1, 0] * Xc + Bi[1, 1] * Yc + dy
        uu = (u % 1.0) * TILE
        vv = (v % 1.0) * TILE
        i0 = uu.astype(np.int32) % TILE; j0 = vv.astype(np.int32) % TILE
        i1 = (i0 + 1) % TILE; j1 = (j0 + 1) % TILE
        fu = (uu - np.floor(uu))[..., None] if False else (uu - uu.astype(np.int32))
        fv = vv - vv.astype(np.int32)
        T = tiles[idx]
        return (T[i0, j0] * (1 - fu) * (1 - fv) + T[i1, j0] * fu * (1 - fv)
                + T[i0, j1] * (1 - fu) * fv + T[i1, j1] * fu * fv)

    # Franja oscura arriba y abajo, hecha en la escena y no solo en el
    # overlay: sobre los patrones claros (p3m1, p6 y p4m salen en crema) el
    # degradado del scrim ya llega debil a la altura del texto y la cabecera
    # se vuelve ilegible.
    yr = (np.arange(H) / H).astype(np.float32)
    def smooth(t):
        t = np.clip(t, 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)
    ramp = (0.15 + 0.85 * smooth(yr / 0.285))
    ramp *= (0.80 + 0.20 * smooth((1.0 - yr) / 0.115))
    ramp = ramp[:, None, None].astype(np.float32)

    shown, events = [], []
    scale_note = ["C3", "E3", "G3", "B3", "C4", "E4", "G4", "B4"]

    for f in range(FRAMES):
        idx = len(order) - 1
        for i in range(len(order)):
            if f < bounds[i + 1]:
                idx = i
                break
        loc = f - bounds[idx]
        dx, dy = 0.055 * f / FPS, 0.032 * f / FPS
        v = sample(idx, dx, dy)
        if loc < FADE and idx > 0:
            a = (loc + 1) / (FADE + 1)
            a = a * a * (3 - 2 * a)
            v = sample(idx - 1, dx, dy) * (1 - a) + v * a
        shown.append(idx)

        img = colorize(v) * ramp
        img = np.clip(img + 0.22 * gaussian_filter(img, (1.1, 1.1, 0)), 0.0, 1.0)
        Image.fromarray((img * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[wp] {f + 1}/{FRAMES}  {metas[idx]['name']}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "groups": metas, "shown": shown, "bounds": bounds,
                   "total": len(order)}, jf)
    print(f"[wp] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
