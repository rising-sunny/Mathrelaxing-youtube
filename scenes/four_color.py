"""
El teorema de los cuatro colores, en un mapa de 2000 paises.

Todo mapa en el plano se puede colorear con cuatro colores sin que dos paises
vecinos compartan color. Se conjeturo en 1852, se demostro en 1976 con ayuda
de computadora (1482 configuraciones), se simplifico en 1997 (633) y en 2026
aparecio una demostracion nueva (8202 configuraciones) que ademas colorea en
n log n pasos en vez de n^2.

El mapa se colorea desde el centro hacia fuera. Cuando un pais queda rodeado
por los cuatro colores se hace un intercambio de Kempe (1879): se toma la
cadena conexa de paises de dos colores a y b y se intercambian, lo que libera
un color. Kempe creyo que eso bastaba para demostrar el teorema y se le creyo
once anos, hasta que Heawood (1890) mostro que puede fallar. Aqui tambien
falla a veces; esos paises se resuelven con una busqueda exacta local, y el
contador de pantalla lo dice.

Se comprueba, antes de dibujar:
  * la deformacion de las fronteras es un difeomorfismo (det J > 0), asi que
    la adyacencia dibujada es la del grafo de Delaunay, que es plano;
  * la coloracion final usa cuatro colores y ninguna arista los repite;
  * en un raster de alta resolucion del mapa, todo par de paises que se tocan
    es una arista del grafo y tiene colores distintos;
  * un pais rodeado por un anillo impar no admite tres colores (busqueda
    exhaustiva): ahi el cuarto color es obligatorio.

Uso:
    python scenes/four_color.py -- --frames 900 --res 1920 --name shorts_4c
"""
import itertools
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, maximum_filter
from scipy.spatial import Delaunay, cKDTree

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_4c")
FPS = int(arg("--fps", 60))
N = int(arg("--n", 2000))
SEED = int(arg("--seed", 3))
ONLY = {int(x) for x in arg("--only", "").split(",") if x}   # vista previa: solo esos cuadros

T_FIRST = 2.5          # a esta altura van 30 paises
K_FIRST = 30
T_DONE = 11.0          # y aqui los 2000
T_SCAN0, T_SCAN1 = 11.4, 13.8

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

W, H = int(round(RES * 9 / 16)), RES
W -= W % 2
H -= H % 2
MW, MH = 1.0, 16.0 / 9.0                       # el mapa, en unidades de mapa
CORNER = 2.5 / 1080                            # ~2.5 px en la vista completa

PALETTE = np.array([[0.95, 0.66, 0.23],        # ambar
                    [0.17, 0.70, 0.66],        # verde azulado
                    [0.88, 0.34, 0.48],        # rosa
                    [0.42, 0.39, 0.85]],       # indigo
                   np.float32)
BLANK = np.array([0.063, 0.090, 0.165], np.float32)
INK = np.array([0.016, 0.024, 0.047], np.float32)
GOLD = np.array([1.00, 0.84, 0.42], np.float32)
ICE = np.array([0.72, 0.95, 1.00], np.float32)


# --------------------------------------------------------------------------
# El mapa
# --------------------------------------------------------------------------
def make_seeds(rng, lloyd=3):
    p = rng.random((N, 2)) * [MW, MH]
    g = np.stack(np.meshgrid(np.linspace(0, MW, 240),
                             np.linspace(0, MH, int(240 * MH))), -1).reshape(-1, 2)
    for _ in range(lloyd):                      # Lloyd: paises de tamano parejo
        lab = cKDTree(p).query(g)[1]
        cnt = np.bincount(lab, minlength=N)[:, None]
        s = np.stack([np.bincount(lab, weights=g[:, k], minlength=N) for k in (0, 1)], 1)
        p = np.where(cnt > 0, s / np.maximum(cnt, 1), p)
    return p


def make_warp(rng):
    """Campo de deformacion suave: las fronteras dejan de ser rectas y se
    parecen a las de un mapa. Dos octavas de senos al azar."""
    modes = []
    for lam, amp, m in ((0.085, 0.0048, 5), (0.024, 0.0008, 7)):
        for _ in range(m):
            ang = rng.uniform(0, 2 * np.pi)
            k = 2 * np.pi / lam * np.array([math.cos(ang), math.sin(ang)])
            modes.append((k, amp / math.sqrt(m) * rng.normal(size=2),
                          rng.uniform(0, 2 * np.pi)))
    return modes


def warp(x, y, modes):
    wx, wy = x.copy(), y.copy()
    for k, a, ph in modes:
        s = np.sin(k[0] * x + k[1] * y + ph)
        wx += a[0] * s
        wy += a[1] * s
    return wx, wy


def warp_jacobian_min(modes):
    x, y = np.meshgrid(np.linspace(0, MW, 700), np.linspace(0, MH, 1244))
    j11 = np.ones_like(x); j12 = np.zeros_like(x)
    j21 = np.zeros_like(x); j22 = np.ones_like(x)
    for k, a, ph in modes:
        c = np.cos(k[0] * x + k[1] * y + ph)
        j11 += a[0] * c * k[0]; j12 += a[0] * c * k[1]
        j21 += a[1] * c * k[0]; j22 += a[1] * c * k[1]
    return float((j11 * j22 - j12 * j21).min())


def make_graph(p):
    """Grafo de Delaunay (el dual de los paises: plano) mas los contactos de
    esquina.

    Donde cuatro paises forman un cuadrilatero casi inscrito en un circulo,
    la frontera que separa a dos de ellos mide menos de un pixel y en la
    imagen los otros dos parecen tocarse. El teorema no cuenta las esquinas,
    pero en pantalla un empate de color ahi se ve. Se detecta con geometria,
    no con pixeles: la arista de Voronoi que los separa une los circuncentros
    de los dos triangulos y, si es mas corta que CORNER, los dos paises de
    enfrente tambien se colorean distintos."""
    tri = Delaunay(p)
    adj = [set() for _ in range(N)]
    for s in tri.simplices:
        for a, b in itertools.combinations(s, 2):
            adj[a].add(b)
            adj[b].add(a)
    dela = {(a, b) for a in range(N) for b in adj[a] if a < b}
    P = p[tri.simplices]
    ax, ay = P[:, 0, 0], P[:, 0, 1]
    bx, by = P[:, 1, 0], P[:, 1, 1]
    cx, cy = P[:, 2, 0], P[:, 2, 1]
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
    corner = set()
    for si, s in enumerate(tri.simplices):
        for i in range(3):
            nj = tri.neighbors[si, i]
            if nj <= si:
                continue
            if math.hypot(ux[si] - ux[nj], uy[si] - uy[nj]) < CORNER:
                a = int(s[i])
                b = int([x for x in tri.simplices[nj] if x not in s][0])
                corner.add((min(a, b), max(a, b)))
    for a, b in corner:
        adj[a].add(b)
        adj[b].add(a)
    return [sorted(x) for x in adj], set(np.unique(tri.convex_hull).tolist()), dela, corner


# --------------------------------------------------------------------------
# La coloracion
# --------------------------------------------------------------------------
def kempe_chain(col, adj, u, a, b):
    comp, st = {u}, [u]
    while st:
        x = st.pop()
        for y in adj[x]:
            if y not in comp and col[y] in (a, b):
                comp.add(y)
                st.append(y)
    return comp


def local_fix(col, adj, v, r):
    """Backtracking exacto en la bola de radio r alrededor de v (lo de fuera
    queda fijo). Devuelve {pais: (antes, despues)} o None."""
    ball, front = {v}, {v}
    for _ in range(r):
        front = {y for x in front for y in adj[x] if col[y] >= 0 and y not in ball}
        ball |= front
    B = sorted(ball)
    old = {x: int(col[x]) for x in B}
    for x in B:
        col[x] = -1

    def free(x):
        return [k for k in range(4) if all(col[y] != k for y in adj[x])]

    def solve():
        rest = [x for x in B if col[x] < 0]
        if not rest:
            return True
        x = min(rest, key=lambda z: len(free(z)))
        for k in free(x):
            col[x] = k
            if solve():
                return True
        col[x] = -1
        return False

    if solve():
        return {x: (old[x], int(col[x])) for x in B}
    for x in B:
        col[x] = old[x]
    return None


def front_dist(p):
    """Distancia eliptica al centro, con la proporcion del cuadro: el frente
    de color es una elipse alta que llena el 9:16. Con un circulo, media
    pantalla se quedaba vacia arriba y abajo."""
    return np.hypot(p[:, 0] - MW / 2, (p[:, 1] - MH / 2) * (MW / MH))


def four_color(p, adj):
    """Codicioso desde el centro, con intercambios de Kempe y, si se atasca,
    busqueda exacta local. Devuelve la coloracion y la lista de eventos."""
    order = np.argsort(front_dist(p))
    col = np.full(N, -1)
    ev, swaps, stuck = [], 0, []
    for v in order:
        used = {col[u] for u in adj[v] if col[u] >= 0}
        free = [k for k in range(4) if k not in used]
        if free:
            col[v] = free[0]
            ev.append({"kind": "c", "v": int(v), "col": int(free[0])})
            continue
        done = False
        for a, b in itertools.permutations(range(4), 2):
            for u in adj[v]:
                if col[u] != a:
                    continue
                ch = list(kempe_chain(col, adj, u, a, b))
                col[ch] = np.where(col[ch] == a, b, a)
                if a not in {col[w] for w in adj[v] if col[w] >= 0}:
                    ev.append({"kind": "k", "v": int(v),
                               "chain": sorted(int(x) for x in ch), "a": a, "b": b})
                    col[v] = a
                    ev.append({"kind": "c", "v": int(v), "col": int(a)})
                    swaps += 1
                    done = True
                    break
                col[ch] = np.where(col[ch] == a, b, a)      # deshacer
            if done:
                break
        if not done:
            for r in range(1, 9):
                ch = local_fix(col, adj, v, r)
                if ch:
                    stuck.append({"v": int(v), "r": r, "size": len(ch)})
                    ev.append({"kind": "f", "v": int(v),
                               "change": {int(x): list(ab) for x, ab in ch.items()}})
                    break
            else:
                raise RuntimeError(f"no se pudo colorear el pais {v}")
    return col, ev, order, swaps, stuck


# --------------------------------------------------------------------------
# Verificacion
# --------------------------------------------------------------------------
def verify(p, adj, hull, dela, corner, col, modes, tree):
    detj = warp_jacobian_min(modes)
    assert detj > 0.1, f"la deformacion pliega el plano: det J minimo {detj:.3f}"

    assert set(np.unique(col).tolist()) <= {0, 1, 2, 3}, "hay mas de cuatro colores"
    clash = sum(col[a] == col[b] for a, b in dela)
    assert clash == 0, f"{clash} fronteras con el mismo color a ambos lados"
    cclash = sum(col[a] == col[b] for a, b in corner)
    assert cclash == 0, f"{cclash} esquinas con el mismo color"

    # lo que se DIBUJA: la vista completa a la resolucion del video y a 2x
    allowed = dela | corner
    drawn = set()
    for hx in (W, 2 * W):
        hy = int(round(hx * MH))
        x, y = np.meshgrid((np.arange(hx) + 0.5) / hx * MW,
                           (np.arange(hy) + 0.5) / hy * MH)
        wx, wy = warp(x, y, modes)
        lab = tree.query(np.stack([wx.ravel(), wy.ravel()], 1), workers=-1)[1].reshape(hy, hx)
        for A, B in ((lab[:, :-1], lab[:, 1:]), (lab[:-1, :], lab[1:, :])):
            m = A != B
            lo, hi = np.minimum(A[m], B[m]), np.maximum(A[m], B[m])
            drawn |= set(zip(lo.tolist(), hi.tolist()))
    outside = drawn - allowed
    assert not outside, f"{len(outside)} contactos dibujados fuera del grafo: {sorted(outside)[:5]}"
    bad = sum(col[a] == col[b] for a, b in drawn)
    assert bad == 0, f"{bad} contactos dibujados comparten color"

    # tres colores no alcanzan: rueda impar, busqueda exhaustiva
    dadj = [set() for _ in range(N)]
    for a, b in dela:
        dadj[a].add(b)
        dadj[b].add(a)
    odd = [v for v in range(N) if v not in hull and len(dadj[v]) % 2 == 1]
    v = min(odd, key=lambda z: len(dadj[z]))
    wheel = [v] + sorted(dadj[v])
    idx = {x: i for i, x in enumerate(wheel)}
    wedges = [(idx[a], idx[b]) for a in wheel for b in dadj[a] if b in idx and a < b]
    ok3 = sum(all(c[i] != c[j] for i, j in wedges)
              for c in itertools.product(range(3), repeat=len(wheel)))
    ok4 = sum(all(c[i] != c[j] for i, j in wedges)
              for c in itertools.product(range(4), repeat=len(wheel)))
    assert ok3 == 0 and ok4 > 0, f"la rueda de {len(wheel)-1} admite {ok3} coloraciones con 3"
    print(f"[4c] det J minimo {detj:.3f} | {len(dela)} fronteras y {len(corner)} esquinas, "
          f"0 choques | {len(drawn)} contactos dibujados, todos en el grafo, 0 choques | "
          f"{len(odd)} paises en anillo impar; rueda de {len(wheel)-1}: "
          f"{ok3} coloraciones con 3, {ok4} con 4")
    return {"detj_min": detj, "edges": len(dela), "corners": len(corner),
            "drawn_pairs": len(drawn), "odd_wheels": len(odd),
            "interior": N - len(hull), "wheel_size": len(wheel) - 1,
            "wheel_3": ok3, "wheel_4": ok4}


# --------------------------------------------------------------------------
# Tiempo y camara
# --------------------------------------------------------------------------
def count_at(t):
    """Paises coloreados en el instante t: lento al principio, exponencial
    despues, todos en T_DONE."""
    if t <= 0:
        return 0.0
    if t < T_FIRST:
        return K_FIRST * (t / T_FIRST) ** 1.15
    u = min(1.0, (t - T_FIRST) / (T_DONE - T_FIRST))
    return K_FIRST * (N / K_FIRST) ** u


def main():
    rng = np.random.default_rng(SEED)
    p = make_seeds(rng)
    modes = make_warp(rng)
    adj, hull, dela, corner = make_graph(p)
    tree = cKDTree(p)
    col, events, order, swaps, stuck = four_color(p, adj)
    stats = verify(p, adj, hull, dela, corner, col, modes, tree)
    print(f"[4c] {swaps} intercambios de Kempe, {len(stuck)} atascos resueltos "
          f"con busqueda local {[(s['r'], s['size']) for s in stuck]}")

    # instante de cada pais segun su rango radial
    rank = np.empty(N, int)
    rank[order] = np.arange(N)
    ts = np.linspace(0, T_DONE, 20001)
    ks = np.array([count_at(x) for x in ts])
    t_of_rank = np.interp(np.arange(N) + 1, ks, ts)
    dist_sorted = front_dist(p)[order]

    for e in events:
        e["t"] = float(t_of_rank[rank[e["v"]]])
        if e["kind"] in ("k", "f"):
            e["t"] -= 0.10                  # la cadena se ve un instante antes
    tprev = 0.0
    for e in events:                        # el orden de los eventos manda
        e["t"] = max(e["t"], tprev)
        tprev = e["t"]

    # estado por pais para las transiciones
    cur = np.full(N, -1)
    prev = np.full(N, -1)
    tchg = np.full(N, -99.0)
    # un pais nuevo aparece en 0.18 s; un intercambio es INSTANTANEO. Hay
    # cadenas de hasta ~900 paises, y con cualquier fundido el mapa entero se
    # queda unos cuadros a medio camino entre dos colores (oliva, salmon). La
    # red dorada de la cadena ya dice donde fue el cambio.
    tdur = np.full(N, 0.18)
    glow_t = np.full(N, -99.0)
    glow_k = np.zeros(N, int)               # 0 kempe (oro), 1 busqueda (hielo)
    jitter = (1 + 0.07 * rng.normal(size=N)).astype(np.float32)[:, None]

    # la camara sigue al frente de color
    hw_s = None
    ei, n_col, n_sw, n_fx, chain_big = 0, 0, 0, 0, 0
    shown = []
    edges = np.array(sorted(dela))
    ey = (p[edges[:, 0], 1] + p[edges[:, 1], 1]) / 2
    for f in range(FRAMES):
        t = f / FPS
        while ei < len(events) and events[ei]["t"] <= t:
            e = events[ei]
            if e["kind"] == "c":
                v = e["v"]
                prev[v], cur[v], tchg[v], tdur[v] = cur[v], e["col"], e["t"], 0.18
                n_col += 1
            elif e["kind"] == "k":
                for x in e["chain"]:
                    prev[x] = cur[x]
                    cur[x] = e["b"] if cur[x] == e["a"] else e["a"]
                    tchg[x], glow_t[x], glow_k[x], tdur[x] = e["t"], e["t"], 0, 1.0 / FPS
                n_sw += 1
                chain_big = max(chain_big, len(e["chain"]))
            else:
                for x, (a, b) in e["change"].items():
                    x = int(x)
                    prev[x], cur[x] = a, b
                    tchg[x], glow_t[x], glow_k[x], tdur[x] = e["t"], e["t"], 1, 1.0 / FPS
                n_fx += 1
                n_col += 1              # el pais atascado queda coloreado aqui
            ei += 1

        k = count_at(t)
        R = dist_sorted[min(N - 1, max(0, int(k)))] if k >= 1 else dist_sorted[0]
        hw_target = min(0.5, max(0.075, 1.12 * R + 0.02))
        hw_s = hw_target if hw_s is None else hw_s + 0.12 * (hw_target - hw_s)
        hw = hw_s
        cx, cy = MW / 2, MH / 2
        # sin salirse del mapa
        hh = hw * H / W
        cy = min(max(cy, hh), MH - hh)

        if ONLY and f not in ONLY:          # vista previa: el estado avanza igual
            shown.append({"t": t, "colored": n_col, "swaps": n_sw, "stuck": n_fx,
                          "checked": 0, "chain": chain_big})
            continue

        xs = cx + (np.arange(W) + 0.5 - W / 2) / W * 2 * hw
        ys = cy + (np.arange(H) + 0.5 - H / 2) / W * 2 * hw
        X, Y = np.meshgrid(xs, ys)
        wx, wy = warp(X, Y, modes)
        lab = tree.query(np.stack([wx.ravel(), wy.ravel()], 1), workers=-1)[1].reshape(H, W)

        # color por pais, con fundidos
        fade = np.clip((t - tchg) / tdur, 0, 1)[:, None].astype(np.float32)
        fade = fade * fade * (3 - 2 * fade)
        to = np.where((cur >= 0)[:, None], PALETTE[np.maximum(cur, 0)], BLANK)
        fr = np.where((prev >= 0)[:, None], PALETTE[np.maximum(prev, 0)], BLANK)
        rgb = (fr * (1 - fade) + to * fade) * jitter
        tau = 0.40 - 0.28 * (hw - 0.075) / 0.425        # lejos hay muchos seguidos
        g = np.exp(-np.maximum(t - glow_t, 0) / tau) * (t >= glow_t)
        img = rgb[lab]

        # fronteras: mas gruesas de cerca, finas de lejos
        bd = np.zeros((H, W), bool)
        bd[:, :-1] |= lab[:, :-1] != lab[:, 1:]
        bd[:-1, :] |= lab[:-1, :] != lab[1:, :]
        thick = int(round(1 + 2.0 * (0.5 - hw) / 0.425))
        if thick > 1:
            bd = maximum_filter(bd, size=thick)
        bdf = np.clip(1.5 * gaussian_filter(bd.astype(np.float32), 0.6), 0, 1)
        img = img * (1 - bdf[..., None]) + INK * bdf[..., None]

        # resplandor de las cadenas de Kempe y de los atascos
        gl = g[lab].astype(np.float32)
        if gl.max() > 0.01:
            tint = np.where((glow_k[lab] == 0)[..., None], GOLD, ICE)
            ring = gaussian_filter(bd.astype(np.float32) * gl, 1.6)
            img += tint * (0.07 * gl[..., None] + 0.9 * ring[..., None])

        # barrido final: cada frontera se comprueba al pasar la linea
        checked = 0
        if t >= T_SCAN0:
            u = min(1.0, (t - T_SCAN0) / (T_SCAN1 - T_SCAN0))
            yl = u * MH
            checked = int((ey <= yl).sum())
            if u < 1.0:
                py = (ys - yl) / (2 * hw) * W
                band = np.exp(-(py / 22.0) ** 2)[:, None].astype(np.float32)
                img += (band * bdf)[..., None] * np.array([0.55, 1.0, 0.75], np.float32)
                img += band[..., None] * 0.05

        img = np.clip(img, 0, 1)
        Image.fromarray((img * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        shown.append({"t": t, "colored": n_col, "swaps": n_sw, "stuck": n_fx,
                      "checked": checked, "chain": chain_big})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[4c] {f+1}/{FRAMES}  coloreados {n_col}  Kempe {n_sw}  "
                  f"atascos {n_fx}  comprobadas {checked}/{len(edges)}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "n": N,
                   "edges": int(len(edges)), "swaps": swaps,
                   "chain_max": max((len(e["chain"]) for e in events if e["kind"] == "k"), default=0),
                   "chain_median": float(np.median([len(e["chain"]) for e in events if e["kind"] == "k"])),
                   "stuck": stuck, "verify": stats, "shown": shown,
                   "events": [{"frame": int(round(x * FPS)), "note": "A4",
                               "intensity": 0.6} for x in (0.0, T_FIRST, T_DONE)]}, jf)
    print(f"[4c] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
