"""
Murmuracion: decenas de miles de estorninos, cada uno mirando solo a sus 7
vecinos mas cercanos.

Regla de cada pajaro i (vecindad TOPOLOGICA, Ballerini et al. 2008: siempre
los 7 mas cercanos, esten a 1 m o a 10 m):

    alinearse     w_a ( <v_j>/|<v_j>| - v_i/|v_i| ) v0
    acercarse     w_c ( <x_j> - x_i )
    no chocar     w_s sum (x_i - x_j) / |x_i - x_j|^3      (|x_i - x_j| < r_s)
    + atraccion suave al dormidero, control de rapidez, ruido
    + huir del halcon

Nadie dirige la bandada. El orden global que se ve (todas las velocidades
alineadas) se mide en pantalla con el parametro de orden

    phi = | sum v_i / |v_i| | / N          (0 = caos, 1 = todos igual)

La base matematica se comprueba antes de dibujar: el modelo de Vicsek (1995)
en 2-D tiene que pasar de orden (phi ~ 1) a desorden (phi ~ 0) al subir el
ruido, que es la transicion de fase de la que sale todo esto.

Uso:
    python scenes/murmuration.py -- --frames 900 --res 1920 --name shorts_murmur
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates
from scipy.spatial import cKDTree

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_murmur")
FPS = int(arg("--fps", 60))
N = int(arg("--n", 30000))
SEED = int(arg("--seed", 3))
ONLY = {int(x) for x in arg("--only", "").split(",") if x}

H = RES
W = RES * 9 // 16

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "output", NAME)
FRAMES_DIR = os.path.join(OUT, "frames")
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

K_NN = 7                      # alineacion: los 7 mas cercanos
K_COH = 40                    # cohesion: una vecindad algo mayor, si no se hace grumos
V0 = 13.0                     # m/s, crucero de un estornino
SIM_PER_S = 1.5               # segundos simulados por segundo de video
DT = SIM_PER_S / FPS
W_A, W_C, W_S, R_S = 6.0, 0.6, 70.0, 3.2
NOISE = 1.0
K_ZN, K_ZG, BANK = 3.0, 0.3, 2.5

# guion (segundos de video)
T_ORDER = 2.5
T_FALCON = (7.5, 9.6)         # dos pasadas del halcon
T_ROOST = 10.8               # empiezan a bajar a los juncos


# ------------------------------------------------------------ verificacion
def vicsek_phi(eta, n=2500, L=25.0, v0=0.5, steps=600, rng=None):
    """modelo de Vicsek 2-D, radio 1, caja periodica: phi al final"""
    rng = rng or np.random.default_rng(0)
    x = rng.random((n, 2)) * L
    th = rng.uniform(-np.pi, np.pi, n)
    phis = []
    for s in range(steps):
        tree = cKDTree(x, boxsize=L)
        pairs = tree.sparse_distance_matrix(tree, 1.0, output_type="coo_matrix")
        c = np.bincount(pairs.row, np.cos(th[pairs.col]), n) + np.cos(th)
        si = np.bincount(pairs.row, np.sin(th[pairs.col]), n) + np.sin(th)
        th = np.arctan2(si, c) + eta * rng.uniform(-0.5, 0.5, n)
        x = (x + v0 * np.stack([np.cos(th), np.sin(th)], 1)) % L
        if s >= steps - 100:
            phis.append(abs(np.mean(np.exp(1j * th))))
    return float(np.mean(phis))


def verify():
    etas = [0.5, 2.0, 3.5, 5.5]
    phis = [vicsek_phi(e) for e in etas]
    print("[murmur] Vicsek 2-D, densidad 4: " + ", ".join(
        f"ruido {e}: phi {p:.3f}" for e, p in zip(etas, phis)))
    assert phis[0] > 0.85, "con poco ruido tiene que ordenarse"
    assert phis[-1] < 0.15, "con mucho ruido tiene que ser caos"
    assert all(a > b for a, b in zip(phis, phis[1:])), "phi tiene que bajar con el ruido"
    return {"etas": etas, "phis": phis}


# ------------------------------------------------------------- simulacion
def roost_target(t):
    """el punto que atrae a la bandada: pasea en el cielo y al final baja"""
    x = 30 * math.sin(0.55 * t) + 15 * math.sin(1.3 * t + 1)
    y = 20 * math.sin(0.4 * t + 2)
    z = 150 + 25 * math.sin(0.8 * t + 0.5)
    if t > T_ROOST:
        u = min(1.0, (t - T_ROOST) / 1.6)
        x = x * (1 - u) + (-60) * u
        y = y * (1 - u) + 40 * u
        z = z * (1 - u) + (-15) * u
    return np.array([x, y, z])


def falcon_pos(t, anchors):
    """el halcon cae en picada ATRAVESANDO la bandada: cada pasada apunta al
    centro que tenia la bandada cuando empezo, y vuelve a subir"""
    out = []
    for k, t0 in enumerate(T_FALCON):
        u = (t - t0) / 1.3
        if -0.2 <= u <= 1.15 and k in anchors:
            c = anchors[k]
            side = 1 if k == 0 else -1
            out.append(c + np.array([side * (-160 + 320 * u), -8 + 16 * u,
                                     115 * (1 - 2 * u) ** 2 - 5]))
    return out


class Flock:
    def __init__(self, n, rng):
        self.rng = rng
        # caos inicial: pajaros sueltos por todo el cielo, direcciones al azar
        self.x = np.stack([rng.uniform(-200, 200, n), rng.uniform(-120, 120, n),
                           rng.uniform(70, 260, n)], 1)
        d = rng.normal(size=(n, 3))
        d[:, 2] *= 0.3
        self.v = d / np.linalg.norm(d, axis=1, keepdims=True) * V0
        self.alive = np.ones(n, bool)
        self.flap = rng.uniform(0, 2 * np.pi, n)
        self.anchors = {}
        self.falcons = []

    def phi(self):
        v = self.v[self.alive]
        u = v / np.linalg.norm(v, axis=1, keepdims=True)
        return float(np.linalg.norm(u.mean(0)))

    def step(self, t, order_gain):
        x, v = self.x, self.v
        idx = np.nonzero(self.alive)[0]
        xa, va = x[idx], v[idx]
        tree = cKDTree(xa)
        dd, nn = tree.query(xa, K_COH + 1)
        d, nb = dd[:, 1:K_NN + 1], nn[:, 1:K_NN + 1]
        sp = np.linalg.norm(va, axis=1, keepdims=True)
        u = va / sp
        un = u[nb].mean(1)
        un /= np.linalg.norm(un, axis=1, keepdims=True) + 1e-9
        acc = W_A * order_gain * (un - u) * V0
        acc += W_C * (xa[nn[:, 1:]].mean(1) - xa)
        close = d < R_S
        if close.any():
            dx = xa[:, None, :] - xa[nb]
            rep = dx / np.maximum(d, 0.3)[..., None] ** 3 * close[..., None]
            acc += W_S * rep.sum(1)
        # dormidero: guiado GLOBAL, la misma aceleracion para todos. No toca
        # el alineamiento entre vecinos; solo hace girar la bandada entera
        tg = roost_target(t)
        c = xa.mean(0)
        g = tg - c
        dh = np.linalg.norm(g[:2])
        pull = 2.2 if t < T_ROOST else 5.0
        a_g = np.zeros(3)
        a_g[:2] = pull * g[:2] / max(dh, 1.0) * math.tanh(dh / 50.0)
        a_g[2] = (0.06 if t < T_ROOST else 0.25) * np.clip(g[2], -80, 80)
        acc += a_g
        acc[:, :2] += 0.03 * (c[:2] - xa[:, :2])   # la bandada no se desarma
        # volar a la altura de los vecinos: la bandada se vuelve una LAMINA,
        # una membrana por la que las maniobras se propagan como ondas
        acc[:, 2] += K_ZN * (xa[nn[:, 1:], 2].mean(1) - xa[:, 2])
        # y la lamina se ladea en los giros, como un avion (tan(ladeo) = a_lat / g)
        slope = a_g[:2] * BANK / 9.81
        layer = c[2] + (xa[:, :2] - c[:2]) @ slope
        acc[:, 2] += K_ZG * (layer - xa[:, 2])
        # los que se alejan mucho del grupo vuelven (nadie se pierde)
        far = np.linalg.norm(xa - c, axis=1, keepdims=True)
        acc += 1.5 * (c - xa) / np.maximum(far, 1) * np.clip((far - 140) / 60, 0, 1)
        # halcon: huida con alcance de 40 m
        for k, t0 in enumerate(T_FALCON):
            if t >= t0 - 0.26 and k not in self.anchors:
                self.anchors[k] = c.copy()
        self.falcons = falcon_pos(t, self.anchors)
        for P in self.falcons:
            r = xa - P
            rn = np.linalg.norm(r, axis=1, keepdims=True)
            acc += 260.0 * r / np.maximum(rn, 1) * np.exp(-(rn / 40.0) ** 2)
        acc += NOISE * self.rng.normal(size=acc.shape)
        # rapidez: vuelve a V0 (al bajar al dormidero pueden picar mas rapido)
        vt = V0 * (1.0 if t < T_ROOST else 1.25)
        acc += 1.5 * (vt - sp) * u
        va = va + DT * acc
        xa = xa + DT * va
        x[idx], v[idx] = xa, va
        # al llegar a los juncos se posan
        if t > T_ROOST:
            landed = idx[xa[:, 2] < 2.0]
            self.alive[landed] = False
        self.flap += DT * 2 * np.pi * 11.0


# ------------------------------------------------------------------ camara
CAM_D = 200.0                 # distancia de la camara al centro
F_PX = W * 0.5 * CAM_D / 105.0
HORIZON = 0.80                # linea del horizonte, en fraccion de H


def project(x):
    depth = x[:, 1] + CAM_D
    sx = W / 2 + F_PX * x[:, 0] / depth
    # la camara mira un poco hacia arriba: el horizonte queda abajo
    sy = HORIZON * H - F_PX * x[:, 2] / depth
    return sx, sy, depth


def save(f, img):
    if ONLY and f not in ONLY:
        return
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        os.path.join(FRAMES_DIR, f"{f + 1:04d}.png"))


def lerp(a, b, u):
    return np.asarray(a) * (1 - u) + np.asarray(b) * u


def fbm(shape, rng, octaves=5, stretch=(1, 6)):
    """ruido fractal suave, estirado en horizontal (nubes de atardecer)"""
    h, w = shape
    out = np.zeros(shape)
    amp = 1.0
    for o in range(octaves):
        sy, sx = max(2, h // (4 * 2 ** o)), max(2, w // (4 * 2 ** o) // stretch[1] * stretch[0] + 2)
        g = rng.normal(size=(sy + 2, sx + 2))
        yy = np.linspace(1, sy, h)[:, None] * np.ones((1, w))
        xx = np.ones((h, 1)) * np.linspace(1, sx, w)[None, :]
        out += amp * map_coordinates(g, [yy, xx], order=3)
        amp *= 0.55
    out -= out.mean()
    return out / out.std()


class Scenery:
    def __init__(self, rng):
        self.hz = int(HORIZON * H)
        y = np.arange(H) / H
        self.y = y
        # nubes: dos capas de estratos finos, en coordenadas de cielo
        self.cl = fbm((H, 2 * W), rng, stretch=(1, 7))
        self.cl2 = fbm((H, 2 * W), rng, octaves=4, stretch=(1, 10))
        # juncos delante, en matas de alturas distintas
        x = np.arange(W)
        clump = gaussian_filter(rng.random(W), 25)
        clump = (clump - clump.min()) / (clump.max() - clump.min())
        reeds = np.zeros((H, W))
        for _ in range(1400):
            x0 = rng.uniform(0, W)
            c = clump[int(x0)]
            if rng.random() > 0.25 + 0.75 * c:
                continue
            hgt = rng.uniform(0.008, 0.02) * H + c * rng.uniform(0, 0.045) * H
            lean = rng.normal(0, 0.35)
            ys = np.arange(int(self.hz - hgt), self.hz + 3)
            xs = x0 + lean * ((self.hz - ys) / hgt) ** 2 * hgt * 0.12
            ok = (xs >= 0) & (xs < W - 1)
            reeds[ys[ok], xs[ok].astype(int)] = 1
            if rng.random() < 0.3:                       # espiga
                yt = int(self.hz - hgt)
                xt = int(np.clip(x0 + lean * hgt * 0.12, 1, W - 2))
                reeds[max(yt - 11, 0):yt + 1, xt - 1:xt + 2] = 1
        reeds[self.hz - 3:self.hz + 3] = 1               # orilla
        self.reeds = np.clip(gaussian_filter(reeds, 0.55) * 2.4, 0, 1)
        self.stars = (rng.random((H, W)) > 0.99965) * rng.uniform(0.3, 1.0, (H, W))
        self.stars[int(0.45 * H):] = 0
        self.stars = gaussian_filter(self.stars, 0.7) * 4
        self.star_ph = rng.uniform(0, 6.28, (H, W))
        self.ripple = rng.normal(size=(H, 3))

    def sky(self, t):
        u = min(1.0, t / 15.0)                          # del atardecer al anochecer
        top = lerp([0.16, 0.19, 0.42], [0.03, 0.04, 0.13], u)
        mid = lerp([0.80, 0.42, 0.42], [0.30, 0.17, 0.34], u ** 0.8)
        low = lerp([1.00, 0.70, 0.36], [0.85, 0.36, 0.20], u ** 0.9)
        y = self.y[:, None] / HORIZON
        w1 = np.clip(y, 0, 1) ** 1.6
        g = lerp(top, mid, np.clip(w1 * 1.6, 0, 1)[..., None])
        g = lerp(g, low, np.clip((w1 - 0.55) / 0.45, 0, 1)[..., None] ** 1.5)
        img = np.repeat(g, W, axis=1)
        # sol que se hunde y su resplandor
        sx, sy = 0.66 * W, (0.745 + 0.10 * u) * H
        yy, xx = np.mgrid[0:H, 0:W]
        r = np.hypot(xx - sx, (yy - sy) * 1.25)
        glow = (np.exp(-(r / (0.35 * W)) ** 2) * 0.55 + np.exp(-(r / (0.09 * W)) ** 2) * 0.6)
        glow *= (1 - 0.55 * u)
        img += glow[..., None] * np.array([1.0, 0.62, 0.30])
        disk = np.clip((0.028 * W - r) / 2.0, 0, 1) * (yy < self.hz)
        img = lerp(img, np.array([1.6, 1.35, 0.95]), (disk * (1 - 0.3 * u))[..., None])
        # nubes: se desplazan despacio; iluminadas por debajo
        off = int(t * 9)
        c1 = self.cl[:, off:off + W]
        c2 = self.cl2[:, 2 * off:2 * off + W] if 2 * off + W <= 2 * W else self.cl2[:, -W:]
        band = np.exp(-((self.y[:, None] - 0.55) / 0.16) ** 2)
        dens = np.clip(c1 * 0.6 + c2 * 0.4 - 0.35, 0, None) * band
        lit = lerp([1.0, 0.55, 0.45], [0.55, 0.28, 0.45], u)
        dark = lerp([0.45, 0.30, 0.45], [0.10, 0.08, 0.18], u)
        img = lerp(img, lerp(dark, lit, np.clip(0.4 + 0.6 * glow, 0, 1)[..., None]),
                   np.clip(dens * 0.55, 0, 0.8)[..., None])
        # estrellas al anochecer
        if u > 0.6:
            tw = 0.7 + 0.3 * np.sin(self.star_ph + t * 5)
            img += (self.stars * tw * (u - 0.6) / 0.4)[..., None] * np.array([0.9, 0.9, 1.0])
        return img

    def ground(self, img, t):
        u = min(1.0, t / 15.0)
        col = lerp([0.10, 0.06, 0.10], [0.025, 0.02, 0.04], u)
        # lago: agua oscura que refleja el cielo, con la estela del sol
        hz = self.hz
        rows = np.arange(hz, H)
        src = np.clip(2 * hz - rows - 2, 0, hz - 1)
        k = np.clip((rows - hz) / (H - hz), 0, 1)
        shift = (np.sin(rows * 0.7 + t * 2.5) * 2 + self.ripple[rows, 0] * 3.0) * (0.4 + 5 * k)
        xs = np.arange(W)[None, :] + shift[:, None]
        refl = np.stack([map_coordinates(img[..., c], [np.repeat(src[:, None], W, 1), xs],
                                         order=1, mode="nearest") for c in range(3)], -1)
        water = lerp([0.10, 0.08, 0.16], [0.02, 0.02, 0.05], u)
        out = water + refl * (0.5 - 0.3 * k)[:, None, None] * np.array([0.8, 0.85, 1.0])
        # rielado del sol: columna de destellos que se apaga al anochecer
        glit = np.clip(self.ripple[rows, 1:2] + np.sin(rows[:, None] * 1.3 + t * 7), 0, None)
        colx = np.exp(-((np.arange(W)[None, :] - 0.66 * W - shift[:, None] * 0.5)
                        / (0.03 * W + 0.12 * W * k[:, None])) ** 2)
        out += (glit * colx * (0.35 * (1 - u) ** 1.5))[..., None] * np.array([1.0, 0.7, 0.35])
        img[hz:] = out
        # juncos delante de todo
        img[:] = lerp(img, col, self.reeds[..., None])
        return img

def splat(acc, x, y, w):
    xi = np.floor(x).astype(int)
    yi = np.floor(y).astype(int)
    fx, fy = x - xi, y - yi
    ok = (xi >= 0) & (xi < W - 1) & (yi >= 0) & (yi < H - 1)
    xi, yi, fx, fy, w = xi[ok], yi[ok], fx[ok], fy[ok], w[ok]
    for dx, dy, ww in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                       (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        acc += np.bincount((yi + dy) * W + xi + dx, w * ww,
                           minlength=H * W).reshape(H, W)


def main():
    os.makedirs(FRAMES_DIR, exist_ok=True)
    ver = verify() if "--no-verify" not in argv else {}
    rng = np.random.default_rng(SEED)
    fl = Flock(N, rng)
    scen = Scenery(np.random.default_rng(SEED + 1))
    global VIG
    global XX, YY
    yy, xx = np.mgrid[0:H, 0:W]
    XX, YY = xx, yy
    VIG = 1 - 0.35 * (((xx - W / 2) / W) ** 2 + ((yy - H * 0.45) / H) ** 2) * 1.6
    shown = []
    for f in range(FRAMES):
        t = f / FPS
        # al principio la alineacion entra de a poco: del caos al orden
        gain = 0.05 + 0.95 * min(1.0, t / T_ORDER) ** 2
        fl.step(t, gain)
        phi = fl.phi()
        shown.append({"phi": phi, "n": int(fl.alive.sum())})
        if ONLY and f not in ONLY:
            continue
        img = scen.sky(t)
        a = fl.alive
        xa, va = fl.x[a], fl.v[a]
        sx, sy, dp = project(xa)
        # estela corta en la direccion del vuelo y aleteo que titila
        sx2, sy2, _ = project(xa - va * DT * 0.9)
        wgt = (CAM_D / dp) ** 2 * (0.6 + 0.4 * np.abs(np.sin(fl.flap[a])))
        dens = np.zeros((H, W))
        splat(dens, sx, sy, wgt * 0.6)
        splat(dens, 0.5 * (sx + sx2), 0.5 * (sy + sy2), wgt * 0.4)
        # halcon: silueta mayor, alas en ancla segun su rumbo
        hal = []
        for P in fl.falcons:
            px, py, pd = project(P[None, :])
            sc = CAM_D / pd[0]
            ang = np.linspace(-1, 1, 81)
            flapf = 1 + 0.35 * math.sin(t * 40)
            wx = px[0] + ang * 17 * sc
            wy = py[0] - np.abs(ang) ** 0.6 * 7 * sc * flapf + 3
            for dy_ in (-1, 0, 1):
                splat(dens, wx, wy + dy_, np.full(81, 3.0 * sc))
            splat(dens, np.full(21, px[0]), py[0] + np.linspace(-3, 8, 21) * sc,
                  np.full(21, 5.0 * sc))
            hal.append((px[0], py[0], sc))
        dens = gaussian_filter(dens, 0.75)
        # perspectiva aerea: el color del pajaro se mezcla con el cielo
        bird = lerp([0.05, 0.035, 0.06], [0.02, 0.02, 0.04], min(1.0, t / 15))
        img = lerp(img, bird, (1 - np.exp(-dens * 11.0))[..., None])
        # halo tibio alrededor del halcon, para seguirlo con la vista
        for hx, hy, sc in hal:
            r = np.hypot(XX - hx, YY - hy)
            img += (np.exp(-(r / (26 * sc)) ** 2) * 0.22)[..., None] * np.array([1.0, 0.55, 0.25])
        img = scen.ground(img, t)
        # vineta suave
        img *= VIG[..., None]
        img = np.clip(img, 0, 1) ** 0.95
        save(f, img)
        print(f"[murmur] cuadro {f}: phi {phi:.3f}, vivos {int(a.sum())}")
    ev = {"duration_s": FRAMES / FPS, "fps": FPS, "n": N, "k": K_NN,
          "verify": ver, "shown": shown, "t_order": T_ORDER,
          "t_falcon": list(T_FALCON), "t_roost": T_ROOST,
          "events": [{"frame": int(round(x * FPS)), "note": "A4"}
                     for x in (T_FALCON[0], T_FALCON[1], T_ROOST)]}
    os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
    with open(EVENTS, "w", encoding="utf-8") as fh:
        json.dump(ev, fh)


if __name__ == "__main__":
    main()
