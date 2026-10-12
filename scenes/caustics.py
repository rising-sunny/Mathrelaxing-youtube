"""
Causticas: la red de luz que baila en el fondo de una piscina.

Superficie del agua: ecuacion de ondas con amortiguamiento suave,

    h_tt = c^2 lap(h) - gamma h_t       (+ gotas, una piedra y viento)

Luz: rayos verticales del sol que se refractan en la superficie con la ley
de Snell (n = 1.333) y bajan hasta el fondo a profundidad D. Donde los rayos
se juntan el fondo se ilumina: las lineas brillantes son CAUSTICAS, pliegues
del mapa superficie -> fondo (teoria de catastrofes: pliegues y cuspides).

Se comprueba antes de dibujar:
  1) un anillo de ondas se expande a la velocidad c de la ecuacion;
  2) con una superficie senoidal h = A sin(kx), la primera caustica (el
     mapa x -> x' deja de ser inyectivo) aparece a la profundidad focal
         D = 1 / ((1 - 1/n) A k^2)
     medida con Snell exacto, sin aproximar.

Uso:
    python scenes/caustics.py -- --frames 900 --res 1920 --name shorts_caustics
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates, zoom

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_caustics")
FPS = int(arg("--fps", 60))
SEED = int(arg("--seed", 2))
ONLY = {int(x) for x in arg("--only", "").split(",") if x}

H = RES
W = RES * 9 // 16
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "output", NAME)
FRAMES_DIR = os.path.join(OUT, "frames")
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

N_WATER = 1.333
SC = 2                                  # pixeles por celda de la superficie
GY, GX = H // SC, W // SC
C_WAVE = 0.55                           # celdas por subpaso
SUB = 8                                 # subpasos por cuadro
GAMMA = 0.002
DEPTH = float(arg("--depth", 260.0))    # profundidad, en pixeles
HSCALE = float(arg("--hscale", 1.2))    # alto de la ola (unidades de la sim -> pixeles)

# guion (segundos)
T_RAIN = 3.0
T_STONE = 8.5
T_WIND = (9.8, 13.2)


# ---------------------------------------------------------------- ondas
def lap(h):
    return (np.roll(h, 1, 0) + np.roll(h, -1, 0) + np.roll(h, 1, 1) +
            np.roll(h, -1, 1) - 4 * h)


class Water:
    def __init__(self, gy, gx):
        self.h = np.zeros((gy, gx))
        self.hp = np.zeros((gy, gx))

    def step(self, force=None):
        h, hp = self.h, self.hp
        hn = (2 - GAMMA) * h - (1 - GAMMA) * hp + C_WAVE ** 2 * lap(h)
        if force is not None:
            hn += force
        self.hp, self.h = h, hn


def drop(gy, gx, y, x, amp, r):
    yy, xx = np.ogrid[0:gy, 0:gx]
    dy = (yy - y + gy / 2) % gy - gy / 2
    dx = (xx - x + gx / 2) % gx - gx / 2
    return -amp * np.exp(-(dx * dx + dy * dy) / (2 * r * r))


# --------------------------------------------------------------- refraccion
def refract_offsets(hx, hy, depth):
    """rayo vertical que baja; la normal de la superficie es (-hx, -hy, 1).
    Devuelve el desplazamiento horizontal del rayo al llegar al fondo
    (Snell exacto en 3-D)."""
    nz = 1.0 / np.sqrt(1 + hx * hx + hy * hy)
    nx, ny = -hx * nz, -hy * nz
    # incidente d = (0, 0, -1); cos_i = -d.n = nz
    eta = 1.0 / N_WATER
    ci = nz
    k = 1 - eta * eta * (1 - ci * ci)
    ct = np.sqrt(k)
    # t = eta d + (eta ci - ct) n
    tx = (eta * ci - ct) * nx
    ty = (eta * ci - ct) * ny
    tz = -eta + (eta * ci - ct) * nz
    return depth * tx / -tz, depth * ty / -tz


def verify():
    # 1) velocidad de un anillo: radio del maximo contra el tiempo
    g = 512
    wv = Water(g, g)
    wv.h += drop(g, g, g / 2, g / 2, 1.0, 3.0)
    wv.hp[:] = wv.h
    radii, times = [], []
    for s in range(1, 361):
        wv.step()
        if s % 60 == 0:
            prof = np.abs(wv.h[g // 2, g // 2:])
            radii.append(float(np.argmax(prof[20:]) + 20))
            times.append(s)
    v = np.polyfit(times, radii, 1)[0]
    v_err = abs(v / C_WAVE - 1)
    # 2) profundidad focal de una superficie senoidal, con Snell exacto
    A, lam = 2.0, 120.0
    k = 2 * math.pi / lam
    x = np.linspace(0, lam, 20001)
    hx = A * k * np.cos(k * x)
    d_lo, d_hi = 1.0, 5000.0
    for _ in range(60):
        d = 0.5 * (d_lo + d_hi)
        ox, _ = refract_offsets(hx, np.zeros_like(hx), d)
        xp = x + ox
        if np.min(np.diff(xp)) <= 0:          # el mapa se pliega: caustica
            d_hi = d
        else:
            d_lo = d
    d_meas = 0.5 * (d_lo + d_hi)
    d_theory = 1.0 / ((1 - 1 / N_WATER) * A * k * k)
    d_err = abs(d_meas / d_theory - 1)
    print(f"[caust] anillo: {v:.4f} celdas/paso contra c = {C_WAVE} ({v_err * 100:.2f}%) | "
          f"primera caustica a D = {d_meas:.1f}, teoria 1/((1-1/n)Ak^2) = {d_theory:.1f} "
          f"({d_err * 100:.2f}%)")
    assert v_err < 0.03, "los anillos no viajan a la velocidad de la ecuacion"
    assert d_err < 0.02, "la caustica no aparece a la profundidad focal"
    return {"ring_speed": float(v), "c": C_WAVE, "ring_err": float(v_err),
            "focal_measured": float(d_meas), "focal_theory": float(d_theory),
            "focal_err": float(d_err), "A": A, "lambda": lam}


# ------------------------------------------------------------------ dibujo
def tiles(rng):
    """fondo de piscina: azulejos claros con junta y una franja de carril"""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    T = 90.0
    gx = np.abs(((xx + 23) % T) - T / 2) > T / 2 - 2.5
    gy = np.abs(((yy + 41) % T) - T / 2) > T / 2 - 2.5
    grout = (gx | gy).astype(np.float32)
    base = np.array([0.80, 0.93, 0.97])
    ti = ((np.floor((xx + 23) / T) * 7 + np.floor((yy + 41) / T) * 13) % 5) / 5
    img = base * (0.93 + 0.07 * ti)[..., None]
    img *= (1 + 0.03 * gaussian_filter(rng.normal(size=(H, W)), 1.2))[..., None]
    lane = (np.abs(xx - W * 0.5) < 34) & (yy > 0.12 * H) & (yy < 0.94 * H)
    img[lane] = np.array([0.10, 0.20, 0.45])
    tcap = (np.abs(xx - W * 0.5) < 95) & (np.abs(yy - 0.12 * H) < 22)
    img[tcap] = np.array([0.10, 0.20, 0.45])
    img = img * (1 - grout[..., None]) + np.array([0.55, 0.66, 0.72]) * grout[..., None]
    return img


def save(f, img):
    if ONLY and f not in ONLY:
        return
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        os.path.join(FRAMES_DIR, f"{f + 1:04d}.png"))


def caustic_light(hx, hy, depth, rays=2):
    """rayos desde la superficie (rays x rays por pixel), refractados y
    sumados donde caen en el fondo; periodico en los bordes"""
    acc = np.zeros(H * W)
    for oy in range(rays):
        for ox_ in range(rays):
            sy = (oy + 0.5) / rays
            sx = (ox_ + 0.5) / rays
            gx_ = map_coordinates(hx, [YYc + sy, XXc + sx], order=1, mode="wrap")
            gy_ = map_coordinates(hy, [YYc + sy, XXc + sx], order=1, mode="wrap")
            dx, dy = refract_offsets(gx_, gy_, depth)
            px = (XXc + sx + dx) % W
            py = (YYc + sy + dy) % H
            xi = np.floor(px).astype(np.int64)
            yi = np.floor(py).astype(np.int64)
            fx, fy = px - xi, py - yi
            for ddx, ddy, ww in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                                 (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
                acc += np.bincount((((yi + ddy) % H) * W + (xi + ddx) % W).ravel(),
                                   ww.ravel(), minlength=H * W)
    return acc.reshape(H, W) / (rays * rays)


def render(h, floor, t, splash):
    hh = zoom(h, SC, order=3) * HSCALE               # superficie en pixeles
    hx = (np.roll(hh, -1, 1) - np.roll(hh, 1, 1)) * 0.5
    hy = (np.roll(hh, -1, 0) - np.roll(hh, 1, 0)) * 0.5
    light = caustic_light(hx, hy, DEPTH)
    light = gaussian_filter(light, 0.7)
    # el fondo iluminado: luz ambiente + causticas, con absorcion del agua
    lit = floor * (0.42 + 0.62 * light)[..., None]
    water = np.array([0.55, 0.85, 0.95])
    lit = lit * water + 0.03 * np.array([0.0, 0.10, 0.18])
    # lo que ve la camara desde arriba: el fondo desplazado por la refraccion
    ox, oy = refract_offsets(hx, hy, DEPTH * 0.55)
    img = np.stack([map_coordinates(lit[..., c], [YYc + oy, XXc + ox], order=1, mode="wrap")
                    for c in range(3)], -1)
    # brillo del sol en la superficie (especular) y reflejo de cielo (Fresnel)
    nn = np.sqrt(1 + hx * hx + hy * hy)
    sun = np.array([0.18, -0.30, 1.0])
    sun /= np.linalg.norm(sun)
    hv = sun + np.array([0, 0, 1.0])
    hv /= np.linalg.norm(hv)
    ndh = (-hx * hv[0] - hy * hv[1] + hv[2]) / nn
    spec = np.clip(ndh, 0, 1) ** 6000
    slope = np.sqrt(hx * hx + hy * hy)
    img += (spec * 1.6)[..., None] * np.array([1.0, 0.97, 0.9])
    img += (np.clip(slope * 3, 0, 1) * 0.06)[..., None] * np.array([0.8, 0.9, 1.0])
    # salpicaduras: corona blanca un instante en cada impacto
    if splash is not None:
        img += splash[..., None] * np.array([1.0, 1.0, 1.0])
    img = img / (1 + 0.15 * img)                     # tono suave para el brillo
    return np.clip(img, 0, 1) ** 0.95


BREEZE = 0.3
WIND_PEAK = 0.72          # mas alto y las causticas se queman en blanco
WAVES = ((0.050, 0.031), (0.034, -0.047), (0.071, 0.012), (-0.028, 0.061))


def wind_field(f):
    """fuerza de trenes de ondas planas que viajan con la velocidad c"""
    yy, xx = np.ogrid[0:GY, 0:GX]
    out = np.zeros((GY, GX))
    for kk, (ky, kx) in enumerate(WAVES):
        w = C_WAVE * math.hypot(ky, kx)           # relacion de dispersion
        out += np.sin(ky * yy + kx * xx - w * f * SUB + 1.7 * kk)
    return 0.012 * out


def main():
    os.makedirs(FRAMES_DIR, exist_ok=True)
    ver = verify() if "--no-verify" not in argv else {}
    rng = np.random.default_rng(SEED)
    global YYc, XXc
    YYc, XXc = np.mgrid[0:H, 0:W].astype(np.float64)
    floor = tiles(rng)
    wv = Water(GY, GX)
    # arranca con la brisa ya establecida (el bucle no empieza en agua muerta)
    for f0 in range(-240, 0):
        for s_ in range(SUB):
            wv.step(BREEZE * wind_field(f0) if s_ == 0 else None)
    # gotas: cada vez mas seguidas desde T_RAIN
    drops, t = [], T_RAIN
    while t < 12.5:
        drops.append((t, rng.uniform(0, GY), rng.uniform(0, GX), rng.uniform(0.6, 1.2)))
        rate = 1.2 + 9.0 * min(1.0, (t - T_RAIN) / 4.5) ** 2
        if t > 11.0:
            rate *= max(0.05, 1 - (t - 11.0) / 1.5)
        t += rng.exponential(1.0 / rate)
    stone = (T_STONE, GY * 0.55, GX * 0.45)
    shown, splashes = [], []
    di = 0
    for f in range(FRAMES):
        tf = f / FPS
        force = np.zeros((GY, GX))
        while di < len(drops) and drops[di][0] <= tf:
            _, y, x, a = drops[di]
            force += drop(GY, GX, y, x, 3.0 * a, 1.6)
            splashes.append((tf, y * SC, x * SC, 0.6 * a))
            di += 1
        if abs(tf - stone[0]) < 0.5 / FPS:
            force += drop(GY, GX, stone[1], stone[2], 14.0, 6.0)
            splashes.append((tf, stone[1] * SC, stone[2] * SC, 2.5))
        # brisa: trenes de olas suaves siempre; el viento los levanta
        env = BREEZE
        if T_WIND[0] <= tf < T_WIND[1]:
            u = (tf - T_WIND[0]) / (T_WIND[1] - T_WIND[0])
            env += (WIND_PEAK - BREEZE) * math.sin(math.pi * u) ** 2
        force += env * wind_field(f)
        for s in range(SUB):
            wv.step(force if s == 0 else None)
        shown.append({"t": tf})
        if ONLY and f not in ONLY:
            continue
        sp = None
        live = [(t0, y, x, a) for t0, y, x, a in splashes if 0 <= tf - t0 < 0.25]
        if live:
            sp = np.zeros((H, W))
            for t0, y, x, a in live:
                age = (tf - t0) / 0.25
                r = 6 + 40 * a * age
                d = np.hypot(XXc - x, YYc - y)
                sp += a * (1 - age) ** 2 * np.exp(-((d - r) / (2 + 3 * a)) ** 2) * 0.8
        img = render(wv.h, floor, tf, sp)
        save(f, img)
        print(f"[caust] cuadro {f}")
    ev = {"duration_s": FRAMES / FPS, "fps": FPS, "verify": ver, "shown": shown,
          "n_drops": len(drops), "drops": [[float(d[0]), float(d[3])] for d in drops],
          "t_rain": T_RAIN, "t_stone": T_STONE,
          "t_wind": list(T_WIND), "depth_px": DEPTH, "n": N_WATER}
    os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
    with open(EVENTS, "w", encoding="utf-8") as fh:
        json.dump(ev, fh)


if __name__ == "__main__":
    main()
