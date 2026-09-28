"""
El iman de Ising: un espin por pixel, 2 millones de imanes diminutos.

    H = -J sum_<ij> s_i s_j - h sum_i s_i,        s_i = +1 o -1

Cada espin quiere apuntar como sus 4 vecinos; el calor lo desordena. Con
Metropolis (tablero de ajedrez, Taichi en CPU) cada espin se da vuelta con
probabilidad min(1, exp(-dE / T)).

Onsager (1944) lo resolvio exacto en 2-D: por debajo de

    Tc = 2 / ln(1 + sqrt 2) = 2.2692...

aparece una magnetizacion espontanea

    M(T) = (1 - sinh(2/T)^-4)^(1/8)

y por encima no hay ninguna. Eso se MIDE antes de dibujar: la simulacion
tiene que dar la M de la formula por debajo de Tc y ~0 por encima.

Uso:
    python scenes/ising.py -- --frames 900 --res 1920 --name shorts_ising
"""
import json
import math
import os
import sys

import numpy as np
import taichi as ti
from PIL import Image
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_ising")
FPS = int(arg("--fps", 60))
SEED = int(arg("--seed", 11))
ONLY = {int(x) for x in arg("--only", "").split(",") if x}

H = RES
W = RES * 9 // 16
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "output", NAME)
FRAMES_DIR = os.path.join(OUT, "frames")
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

TC = 2.0 / math.log(1.0 + math.sqrt(2.0))

ti.init(arch=ti.cpu, random_seed=SEED)

PX = 3                                       # pixeles por espin (2 no sobrevive a la compresion)
LWID, LHEI = W // PX, H // PX
spin = ti.field(ti.i8, (LWID, LHEI))
heat = ti.field(ti.f32, (LWID, LHEI))        # actividad reciente (vueltas)
T_f = ti.field(ti.f32, ())
h_f = ti.field(ti.f32, ())
LW = ti.field(ti.i32, ())
LH = ti.field(ti.i32, ())


@ti.kernel
def randomize(p_up: ti.f32):
    for i, j in ti.ndrange(LW[None], LH[None]):
        spin[i, j] = ti.cast(1 if ti.random() < p_up else -1, ti.i8)
        heat[i, j] = 0.0


@ti.kernel
def half_sweep(parity: ti.i32, decay: ti.f32):
    w, hh = LW[None], LH[None]
    beta = 1.0 / T_f[None]
    for i, j in ti.ndrange(w, hh):
        if (i + j) % 2 == parity:
            s = ti.cast(spin[i, j], ti.f32)
            nb = ti.cast(spin[(i + 1) % w, j] + spin[(i - 1 + w) % w, j] +
                         spin[i, (j + 1) % hh] + spin[i, (j - 1 + hh) % hh], ti.f32)
            dE = 2.0 * s * (nb + h_f[None])
            heat[i, j] *= decay
            if dE <= 0 or ti.random() < ti.exp(-dE * beta):
                spin[i, j] = ti.cast(-s, ti.i8)
                heat[i, j] += 1.0


@ti.kernel
def magnetization() -> ti.f32:
    m = 0.0
    for i, j in ti.ndrange(LW[None], LH[None]):
        m += ti.cast(spin[i, j], ti.f32)
    return m / (LW[None] * LH[None])


def sweep(n, decay=0.9):
    for _ in range(n):
        half_sweep(0, decay)
        half_sweep(1, decay)


def onsager(T):
    return (1 - math.sinh(2 / T) ** -4) ** 0.125 if T < TC else 0.0


def verify():
    """magnetizacion medida contra Onsager en una red de 256 x 256"""
    LW[None], LH[None] = 256, 256
    h_f[None] = 0.0
    rows = []
    for T in (1.6, 1.9, 2.1, 3.0):
        T_f[None] = T
        randomize(1.0)                       # arranca ordenado: equilibra rapido
        sweep(1500)
        ms = []
        for _ in range(400):
            sweep(2)
            ms.append(abs(magnetization()))
        m = float(np.mean(ms))
        rows.append((T, m, onsager(T)))
    print("[ising] Tc exacta 2/ln(1+sqrt2) = %.4f | " % TC + " | ".join(
        f"T={T}: M medida {m:.4f}, Onsager {o:.4f}" for T, m, o in rows))
    for T, m, o in rows[:3]:
        assert abs(m - o) < 0.01, f"a T={T} la magnetizacion no da la de Onsager"
    assert rows[3][1] < 0.05, "por encima de Tc no deberia haber magnetizacion"
    return {"tc": TC, "rows": rows}


# ------------------------------------------------------------------ guion
def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


T_FIELD = 9.5
H_FIELD = 0.35            # contra la mayoria: nuclean gotas y se come todo
H_HELP = 0.12             # antes, a favor de la mayoria: el iman se uniforma
T_LOW = 1.2               # en frio la nucleacion es rara y cada gota crece grande


def schedule(t):
    """temperatura, |campo| y barridos por cuadro para el segundo t.
    El signo del campo lo pone main segun la magnetizacion."""
    pts = [(0.0, 4.5), (2.5, 3.0), (5.5, TC), (7.0, TC), (8.0, 1.6), (9.0, 1.6),
           (9.5, T_LOW), (12.6, T_LOW), (15.0, 4.5)]
    for (t0, a), (t1, b) in zip(pts, pts[1:]):
        if t <= t1:
            T = a + (b - a) * smooth((t - t0) / (t1 - t0))
            break
    else:
        T = pts[-1][1]
    help_, h = 0.0, 0.0
    if 8.0 <= t < T_FIELD:
        help_ = H_HELP * smooth((t - 8.0) / 0.5)
    if T_FIELD <= t < 12.6:
        h = H_FIELD * smooth((t - T_FIELD) / 0.25)
    elif t >= 12.6:
        h = H_FIELD * (1 - smooth((t - 12.6) / 1.0))
    if T_FIELD <= t < 12.6:
        n = 2                               # la avalancha, a camara lenta
    else:
        n = 6 if T > 2.6 else (12 if T > 2.0 else 14)
    return T, help_, h, n


# ------------------------------------------------------------------ dibujo
def save(f, img):
    if ONLY and f not in ONLY:
        return
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        os.path.join(FRAMES_DIR, f"{f + 1:04d}.png"))


UP_DARK = np.array([0.02, 0.07, 0.30])
UP_LITE = np.array([0.12, 0.45, 1.00])
DN_DARK = np.array([0.30, 0.04, 0.05])
DN_LITE = np.array([1.00, 0.48, 0.12])


def render(s, act, T):
    s = s.T.astype(np.float32)[::-1]                 # (filas, columnas), y hacia arriba
    act = act.T[::-1]
    # cada espin es un bloque de PX x PX pixeles, nitido
    s = np.repeat(np.repeat(s, PX, 0), PX, 1)
    act = np.repeat(np.repeat(act, PX, 0), PX, 1)
    u = (gaussian_filter(s, 0.45) + 1) / 2
    # lejos de un borde el dominio se ve mas profundo y calmo
    depth = np.abs(gaussian_filter(s, 7.0))
    up = UP_LITE + (UP_DARK - UP_LITE) * (0.75 * depth)[..., None]
    dn = DN_LITE + (DN_DARK - DN_LITE) * (0.75 * depth)[..., None]
    img = dn * (1 - u)[..., None] + up * u[..., None]
    # las paredes, donde hay vueltas coherentes, se encienden; el ruido termico
    # solo titila (el brillo local promedia la actividad de la zona)
    loc = gaussian_filter(act, 3.0)
    wall = np.abs(gaussian_filter(s, 1.5)) < 0.6      # cerca de un borde
    glow = (1 - np.exp(-loc * 0.35)) * np.where(wall, 1.0, 0.25)
    glow *= min(1.0, max(0.12, (3.0 - T) / 0.8))      # en caliente, poco brillo
    img += gaussian_filter(glow, 1.0)[..., None] * np.array([1.0, 0.90, 0.75]) * 0.55
    img += gaussian_filter(glow, 12)[..., None] * np.array([0.5, 0.6, 1.0]) * 0.35
    return np.clip(img, 0, 1) ** 0.95


def main():
    os.makedirs(FRAMES_DIR, exist_ok=True)
    ver = verify() if "--no-verify" not in argv else {}
    LW[None], LH[None] = LWID, LHEI
    randomize(0.5)
    shown = []
    sign = s_help = None
    for f in range(FRAMES):
        t = f / FPS
        T, help_, h, n = schedule(t)
        if t >= 8.0 and s_help is None:
            s_help = 1.0 if magnetization() > 0 else -1.0
        if t >= T_FIELD and sign is None:
            sign = -1.0 if magnetization() > 0 else 1.0
        h = help_ * (s_help or 0.0) + h * (sign or 0.0)
        T_f[None], h_f[None] = T, h
        sweep(n, decay=0.55 ** (1.0 / n))            # el brillo dura ~ un cuadro
        M = magnetization()
        shown.append({"T": T, "h": h, "M": float(M)})
        if ONLY and f not in ONLY:
            continue
        img = render(spin.to_numpy(), heat.to_numpy(), T)
        save(f, img)
        print(f"[ising] cuadro {f}: T {T:.3f}, h {h:+.2f}, M {M:+.3f}")
    ev = {"duration_s": FRAMES / FPS, "fps": FPS, "w": W, "h": H, "verify": ver,
          "shown": shown, "tc": TC, "t_field": T_FIELD, "h_field": H_FIELD}
    os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
    with open(EVENTS, "w", encoding="utf-8") as fh:
        json.dump(ev, fh)


if __name__ == "__main__":
    main()
