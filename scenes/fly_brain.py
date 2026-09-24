"""
El cerebro de una mosca real, simulado neurona por neurona.

Posiciones y cableado: FlyEM MaleCNS v1.0 (Janelia Research Campus, 2026,
CC-BY), el conectoma completo del sistema nervioso central de una mosca
macho: 164587 neuronas trazadas y 124 millones de sinapsis. Modelo: el de
Shiu et al., Nature 2024 (integrar y disparar con fuga, sinapsis alfa), que
es el que usan las simulaciones virales de septiembre de 2026. Ver
fly_brain_sim.py.

Se estimulan los detectores de objetos que se acercan (LPLC2 y LC4, en los
lobulos opticos) y se mira que pasa. La Fibra Gigante, la neurona del
escape, dispara a los ~3 ms; la motoneurona del salto (TTMn), abajo en el
cordon nervioso ventral, a los ~10 ms. La de alimentacion (MN9) no se
mueve: el control de que el circuito es especifico.

Comprobado antes de dibujar:
  * el integrador reproduce la formula cerrada del potencial postsinaptico
    (error ~1e-13 mV) y la frecuencia analitica con corriente constante;
  * la Fibra Gigante dispara antes que la motoneurona del salto, esta
    dispara, y la de alimentacion queda en silencio, con dos semillas
    distintas del estimulo.

Uso:
    python scenes/fly_brain.py -- --frames 900 --res 1920 --name shorts_fly
"""
import json
import math
import os
import sys
import urllib.request

import numpy as np
import scipy.sparse as sp
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fly_brain_sim as S  # noqa: E402

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_fly")
FPS = int(arg("--fps", 60))
SEED = int(arg("--seed", 1))
ONLY = {int(x) for x in arg("--only", "").split(",") if x}
T_BIO = 300.0                                   # ms simulados

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = arg("--data", os.path.join(REPO, "data", "malecns"))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)

W, H = int(round(RES * 9 / 16)), RES
W -= W % 2
H -= H % 2

BUCKET = ("https://storage.googleapis.com/flyem-male-cns/v1.0/"
          "connectome-data/flat-connectome/")
FILES = ["body-annotations-male-cns-v1.0-minconf-0.5.feather",
         "body-neurotransmitters-male-cns-v1.0.feather",
         "connectome-weights-male-cns-v1.0-minconf-0.5-traced-only.feather"]

# linea de tiempo: segundo de video -> milisegundo biologico
T_STIM = 1.8           # entra el estimulo
T_FAST = 13.0          # a esta altura van 200 ms biologicos
B_FAST = 200.0
KEXP = 5.0             # camara lenta exponencial: el primer ms dura ~1.6 s


def bio_ms(t):
    if t < T_STIM:
        return -1.0
    if t <= T_FAST:
        u = (t - T_STIM) / (T_FAST - T_STIM)
        return B_FAST * (math.exp(KEXP * u) - 1) / (math.exp(KEXP) - 1)
    return B_FAST + (t - T_FAST) * 30.0         # el final, a 30 ms por segundo


def fetch():
    os.makedirs(DATA, exist_ok=True)
    for f in FILES:
        p = os.path.join(DATA, f)
        if not os.path.exists(p):
            print(f"[fly] descargando {f} ...")
            urllib.request.urlretrieve(BUCKET + f, p)


def positions(bodies, ann, Wm):
    """Soma de cada neurona en voxeles de 8 nm. Unas 25000 no tienen posicion
    de soma en los datos: el 63% son sensoriales, con el cuerpo celular fuera
    del sistema nervioso (ojo, patas, trompa), y el resto sobre todo del
    lobulo optico sin anotar. Se dibujan en el centro de masa de sus
    companeras de sinapsis, que es donde conectan."""
    has = ann["somaLocation"].notna().values
    P = np.zeros((len(bodies), 3))
    P[has] = np.stack(ann.loc[has, "somaLocation"].values).astype(float)
    A = abs(Wm) + abs(Wm).T
    known = has.astype(float)
    for _ in range(3):
        wsum = A @ known
        est = (A @ (P * known[:, None])) / np.maximum(wsum, 1e-9)[:, None]
        fill = (known == 0) & (wsum > 0)
        P[fill] = est[fill]
        known = np.maximum(known, fill.astype(float))
    return P, has, known > 0


def verify_circuit(Wm, stim, gf, tt, mn9):
    """Dos semillas del estimulo: la Fibra Gigante dispara antes que el
    salto, el salto dispara, y la alimentacion queda en silencio."""
    out = []
    for seed in (11, 12):
        st, si = S.simulate(Wm, stim, 60.0, np.random.default_rng(seed))
        first = lambda ix: min((float(st[si == i].min()) * S.DT for i in ix if np.any(si == i)),
                               default=None)
        g, t, m = first(gf), first(tt), first(mn9)
        out.append((g, t, m))
        assert g is not None and t is not None, f"semilla {seed}: GF {g}, TTMn {t}"
        assert g < t, f"semilla {seed}: el salto ({t} ms) antes que la Fibra Gigante ({g} ms)"
        assert m is None, f"semilla {seed}: la neurona de alimentacion disparo a los {m} ms"
    print("[fly] circuito con dos semillas: " + " | ".join(
        f"GF {g:.1f} ms, salto {t:.1f} ms, alimentacion en silencio" for g, t, _ in out))
    return out


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------
PALETTE = {"ol": (0.10, 0.55, 0.85), "vis": (0.10, 0.55, 0.85),
           "cb": (0.48, 0.36, 0.98), "vnc": (0.30, 0.52, 1.00),
           "other": (0.55, 0.50, 0.75)}
FLASH = np.array([1.00, 0.86, 0.58], np.float32)
COOL = np.array([0.72, 0.95, 1.00], np.float32)
GF_C = np.array([1.00, 0.78, 0.30], np.float32)
JUMP_C = np.array([1.00, 0.36, 0.62], np.float32)


def base_colors(ann):
    sc = ann["superclass"].fillna("").astype(str).to_numpy(dtype=object)
    col = np.empty((len(sc), 3), np.float32)
    for i, s in enumerate(sc):
        if s.startswith("ol_") or s.startswith("visual"):
            col[i] = PALETTE["ol"]
        elif s.startswith("cb_"):
            col[i] = PALETTE["cb"]
        elif s.startswith("vnc_") or s.startswith("sensory_asc"):
            col[i] = PALETTE["vnc"]
        else:
            col[i] = PALETTE["other"]
    return col


def splat(x, y, wgt, h, w):
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx, fy = x - x0, y - y0
    out = np.zeros(h * w, np.float64)
    for dx, dy, ww in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                       (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xi, yi = x0 + dx, y0 + dy
        ok = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
        out += np.bincount(yi[ok] * w + xi[ok], weights=(wgt * ww)[ok], minlength=h * w)
    return out.reshape(h, w).astype(np.float32)


def main():
    fetch()
    ver = S.verify()
    bodies, Wm, ann, stats = S.load(DATA)
    print(f"[fly] red: {stats}")
    stim = S.ids_of(ann, bodies, ["LPLC2", "LC4"])
    gf = S.ids_of(ann, bodies, ["DNp01"])
    tt = S.ids_of(ann, bodies, ["TTMn"])
    mn9 = S.ids_of(ann, bodies, ["MN9"])
    assert len(gf) == 2 and len(tt) == 2 and len(mn9) == 2 and len(stim) > 300
    syn_gf_tt = [[int(round(abs(Wm[a, b]) / S.WSYN)) for b in gf] for a in tt]
    circ = verify_circuit(Wm, stim, gf, tt, mn9)

    P, has_soma, placed = positions(bodies, ann, Wm)
    print(f"[fly] {int(has_soma.sum())} somas reales; {int((placed & ~has_soma).sum())} "
          f"colocadas en el centro de sus sinapsis")

    # la simulacion que se dibuja
    st, si = S.simulate(Wm, stim, T_BIO, np.random.default_rng(SEED))
    t_ms = st * S.DT
    order = np.argsort(t_ms, kind="stable")
    t_ms, si = t_ms[order], si[order]
    first_gf = float(min(t_ms[si == i].min() for i in gf))
    first_tt = float(min(t_ms[si == i].min() for i in tt if np.any(si == i)))
    print(f"[fly] corrida del video: {len(si)} espigas, {len(np.unique(si))} neuronas "
          f"activas; Fibra Gigante a {first_gf:.1f} ms, salto a {first_tt:.1f} ms")

    # geometria: z es el eje largo (cerebro arriba, cordon abajo)
    # centro de la CAJA, no de masa: casi todas las neuronas estan en el
    # cerebro, y centrando en la masa el cordon ventral se salia por abajo
    lo, hi = P[placed].min(axis=0), P[placed].max(axis=0)
    c = (lo + hi) / 2
    Q = P - c
    scale = 1.0 / 98.0                                  # pixeles por voxel
    base = base_colors(ann)
    # el cordon ventral tiene diez veces menos neuronas que el cerebro: en
    # reposo se perdia. Se le da mas peso por neurona.
    sc = ann["superclass"].fillna("").astype(str).to_numpy(dtype=object)
    boost = np.where([x.startswith("vnc_") for x in sc], 2.2, 1.0)
    stim_mask = np.zeros(len(bodies), bool)
    stim_mask[stim] = True

    # aristas que se dibujan: detectores -> Fibra Gigante, Fibra -> salto
    edges = []
    for g in gf:
        col = Wm[g, :].tocoo()
        for j, wv in zip(col.col, col.data):
            if stim_mask[j] and wv > 0:
                edges.append((int(j), int(g), float(wv)))
    for a in tt:
        for b in gf:
            if Wm[a, b] > 0:
                edges.append((int(b), int(a), float(Wm[a, b])))
    edges = np.array(edges)
    print(f"[fly] {len(edges)} conexiones dibujadas (detectores a la Fibra, Fibra al salto)")

    glow = np.zeros(len(bodies), np.float32)
    ever = np.zeros(len(bodies), bool)
    ring_gf = ring_tt = None
    shown = []
    k_prev = 0
    for f in range(FRAMES):
        t = f / FPS
        b = bio_ms(t)
        k_now = int(np.searchsorted(t_ms, b, side="right")) if b >= 0 else 0
        fired = si[k_prev:k_now]
        k_prev = k_now
        glow *= math.exp(-1.0 / FPS / 0.22)
        if len(fired):
            np.add.at(glow, fired, 1.0)
            np.minimum(glow, 1.2, out=glow)
            ever[fired] = True
        if ring_gf is None and np.isin(gf, fired).any():
            ring_gf = t
        if ring_tt is None and np.isin(tt, fired).any():
            ring_tt = t

        n_active = int(ever.sum())
        shown.append({"t": t, "bio_ms": b, "active": n_active,
                      "gf": ring_gf is not None, "jump": ring_tt is not None})
        if ONLY and f not in ONLY:
            continue

        yaw = 0.62 * math.sin(2 * math.pi * t / 15.0) + 0.15
        cy_, sy_ = math.cos(yaw), math.sin(yaw)
        X = Q[:, 0] * cy_ + Q[:, 1] * sy_
        D = -Q[:, 0] * sy_ + Q[:, 1] * cy_               # profundidad
        Z = Q[:, 2]
        px = W / 2 + X * scale
        py = 0.54 * H + Z * scale
        dn = (D - D.min()) / (D.max() - D.min() + 1e-9)
        depth = (0.55 + 0.45 * (1 - dn)).astype(np.float32)

        img = np.zeros((H, W, 3), np.float32)
        # reposo: todas las neuronas, tenues, por region
        m = placed
        # color de reposo: un splat por canal
        for ch in range(3):
            wr = 0.062 * depth[m] * base[m, ch] * boost[m]
            layer = splat(px[m], py[m], wr.astype(np.float64), H, W)
            img[..., ch] += gaussian_filter(layer, 0.9) * 2.6 + gaussian_filter(layer, 4.0) * 1.2

        # destellos
        act = glow > 0.02
        if act.any():
            ix = np.nonzero(act & placed)[0]
            wv = (glow[ix] * depth[ix]).astype(np.float64)
            hot = splat(px[ix], py[ix], wv, H, W)
            core = gaussian_filter(hot, 1.1)
            halo = gaussian_filter(hot, 5.5)
            cool = stim_mask[ix]
            if cool.any():
                hc = splat(px[ix[cool]], py[ix[cool]], wv[cool], H, W)
                core_c = gaussian_filter(hc, 1.1)
                core = core - core_c
                img += (2.0 * core_c)[..., None] * COOL * 0.55
            img += (2.0 * np.maximum(core, 0))[..., None] * FLASH
            img += (0.42 * halo)[..., None] * FLASH * np.array([1.0, 0.8, 0.6], np.float32)

        # aristas: cuando el presinaptico brilla, su conexion se enciende
        lay = Image.new("L", (W * 2, H * 2), 0)
        dr = ImageDraw.Draw(lay)
        for j, g, wv in edges:
            j, g = int(j), int(g)
            a = float(glow[j])
            if a < 0.05:
                continue
            lvl = int(min(255, 60 + 70 * a * min(1.0, wv / 10.0)))
            dr.line([(px[j] * 2, py[j] * 2), (px[g] * 2, py[g] * 2)], fill=lvl, width=2)
        lines = np.asarray(lay.resize((W, H), Image.BILINEAR)).astype(np.float32) / 255.0
        img += (0.30 * lines)[..., None] * GF_C

        # anillos: la Fibra Gigante y el salto, la primera vez que disparan
        for t0, ids, colr in ((ring_gf, gf, GF_C), (ring_tt, tt, JUMP_C)):
            if t0 is None or t - t0 > 1.6:
                continue
            u = (t - t0) / 1.6
            rad = 14 + 150 * u
            yy, xx = np.ogrid[:H, :W]
            for i in ids:
                d = np.sqrt((xx - px[i]) ** 2 + (yy - py[i]) ** 2)
                ring = np.exp(-((d - rad) / 4.0) ** 2) * (1 - u) ** 1.5
                img += (0.9 * ring)[..., None] * colr
                img += (np.exp(-(d / 9.0) ** 2) * 1.6 * (1 - u))[..., None] * colr

        out = 1.0 - np.exp(-1.35 * np.maximum(img, 0))
        bg = np.array([0.012, 0.014, 0.030], np.float32)
        out = np.clip(out + bg, 0, 1)
        Image.fromarray((out * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[fly] {f+1}/{FRAMES}  t_bio {b:7.2f} ms  activas {n_active}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "stats": stats,
                   "verify": ver, "circuit": circ, "syn_gf_ttmn": syn_gf_tt,
                   "n_stim": int(len(stim)), "somas": int(has_soma.sum()),
                   "spikes": int(len(si)), "active_total": int(len(np.unique(si))),
                   "first_gf_ms": first_gf, "first_jump_ms": first_tt,
                   "shown": shown,
                   "events": [{"frame": int(round(x * FPS)), "note": "D3", "intensity": 0.7}
                              for x in (0.0, T_STIM)]}, jf)
    print(f"[fly] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
