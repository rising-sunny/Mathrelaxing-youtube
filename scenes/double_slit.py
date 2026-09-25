"""
Doble rendija: un electron a la vez, con la ecuacion de Schrodinger.

    i dpsi/dt = -1/2 lap(psi) + V psi          (hbar = m = 1, unidades de celda)

Split-step de Fourier (Strang): medio paso de potencial, paso cinetico exacto
en el espacio de momentos, medio paso de potencial. V es una pared real con
dos rendijas; los bordes llevan un potencial absorbente para que la onda no
de la vuelta por la periodicidad de la FFT.

La pantalla es una fila del dominio: ahi se acumula el flujo de probabilidad
j_y = Im(psi* dpsi/dy) a lo largo de toda la simulacion. Esa P(x), MEDIDA, es
la que decide donde cae cada electron despues del colapso.

Se comprueba antes de dibujar nada:
  1) unitariedad: la norma del paquete libre no cambia (error de redondeo);
  2) dispersion libre: el ancho sigue sigma0 sqrt(1 + (t / 2 sigma0^2)^2);
  3) energia <H> conservada con la pared puesta;
  4) los maximos medidos en la pantalla caen en sin(theta) = n lambda / d.

Uso:
    python scenes/double_slit.py -- --frames 900 --res 1920 --name shorts_slit
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import fft as sfft
from scipy.ndimage import gaussian_filter, zoom

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_slit")
FPS = int(arg("--fps", 60))
SEED = int(arg("--seed", 7))
ONLY = {int(x) for x in arg("--only", "").split(",") if x}
NDOTS = int(arg("--ndots", 50000))

H = RES
W = RES * 9 // 16
SC = 1.5                                    # pixeles por celda
NY, NX = int(round(H / SC)), int(round(W / SC))

# geometria, en fraccion de la altura (y crece hacia abajo)
Y_PLATE0, Y_PLATE1 = 0.200, 0.325           # placa detectora (solo dibujo)
Y_SCREEN = 0.330                            # fila donde se mide el flujo
Y_WALL = 0.660
Y_SRC = 0.835
LAM_PX = 24.0                               # longitud de onda de de Broglie
D_PX = 112.0                                # separacion entre rendijas
A_PX = 28.0                                 # ancho de cada rendija
WALL_PX = 9.0
SIGX_PX, SIGY_PX = 250.0, 60.0

LAM = LAM_PX / SC
K0 = 2 * math.pi / LAM
D, A = D_PX / SC, A_PX / SC
DT = 0.5                                     # con 1.0 la pared rompe la energia (x1.8)
V_WALL = 2.0                                # >> E = k0^2/2 ~ 0.14
CAP_W, CAP_ETA = 60.0, 0.06

T_COLLAPSE = float(arg("--t-collapse", 6.0))
COLLAPSE_FRAC = 0.40                        # fraccion del flujo que ya llego

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "output", NAME)
FRAMES_DIR = os.path.join(OUT, "frames")
CACHE = os.path.join(OUT, "pass1.npz")
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")


# ---------------------------------------------------------------- simulacion
def kinetic(ny, nx, dt):
    ky = 2 * np.pi * sfft.fftfreq(ny)
    kx = 2 * np.pi * sfft.fftfreq(nx)
    return np.exp(-0.5j * dt * (ky[:, None] ** 2 + kx[None, :] ** 2))


def wall_potential(ny, nx):
    y = np.arange(ny)[:, None] + 0.5
    x = np.arange(nx)[None, :] + 0.5 - nx / 2
    yw = Y_WALL * ny
    band = np.abs(y - yw) < (WALL_PX / SC) / 2
    open_ = (np.abs(np.abs(x) - D / 2) < A / 2)
    V = np.where(band & ~open_, V_WALL, 0.0)
    return V


def absorber(ny, nx):
    y = np.arange(ny)[:, None] + 0.5
    x = np.arange(nx)[None, :] + 0.5
    ys = Y_SCREEN * ny
    # arriba: empieza un poco por encima de la pantalla, para medir limpio
    top = np.clip((ys - 8 - y) / CAP_W, 0, None)
    bot = np.clip((y - (ny - CAP_W)) / CAP_W, 0, None)
    lft = np.clip((CAP_W - x) / CAP_W, 0, None)
    rgt = np.clip((x - (nx - CAP_W)) / CAP_W, 0, None)
    d = np.maximum(np.maximum(np.minimum(top, 1.5), bot), np.maximum(lft, rgt))
    return np.exp(-CAP_ETA * d ** 2 * DT)


def packet(ny, nx, y0, x0=None, sx=None, sy=None, k=K0):
    y = np.arange(ny)[:, None] + 0.5
    x = np.arange(nx)[None, :] + 0.5
    x0 = nx / 2 if x0 is None else x0
    sx = SIGX_PX / SC if sx is None else sx
    sy = SIGY_PX / SC if sy is None else sy
    psi = (np.exp(-(x - x0) ** 2 / (4 * sx ** 2) - (y - y0) ** 2 / (4 * sy ** 2))
           * np.exp(-1j * k * y))                        # viaja hacia arriba
    return psi / math.sqrt(float(np.sum(np.abs(psi) ** 2)))


class Sim:
    def __init__(self, ny, nx, V, mask=None, dt=DT):
        self.T = kinetic(ny, nx, dt)
        self.P = np.exp(-0.5j * dt * V)
        if mask is not None:
            self.P = self.P * np.sqrt(mask)              # medio paso cada lado
        self.V = V

    def step(self, psi):
        psi = psi * self.P
        psi = sfft.ifft2(sfft.fft2(psi, workers=-1) * self.T, workers=-1)
        return psi * self.P

    def energy(self, psi):
        ky = 2 * np.pi * sfft.fftfreq(psi.shape[0])
        kx = 2 * np.pi * sfft.fftfreq(psi.shape[1])
        ph = sfft.fft2(psi, workers=-1)
        kin = 0.5 * np.sum(np.abs(ph) ** 2 * (ky[:, None] ** 2 + kx[None, :] ** 2)) / psi.size
        return float(kin + np.sum(self.V * np.abs(psi) ** 2))


def verify():
    ny, nx = 256, 256
    zero = np.zeros((ny, nx))
    # 1) y 2): paquete libre, quieto (k = 0) para que no salga de la caja
    s0 = 6.0
    psi = packet(ny, nx, ny / 2, sx=s0, sy=s0, k=0.0)
    sim = Sim(ny, nx, zero)
    n0 = float(np.sum(np.abs(psi) ** 2))
    xs = np.arange(nx) + 0.5 - nx / 2
    t_end = 120.0
    for _ in range(int(round(t_end / DT))):
        psi = sim.step(psi)
    norm_err = abs(float(np.sum(np.abs(psi) ** 2)) - n0)
    px = np.sum(np.abs(psi) ** 2, axis=0)
    sig = math.sqrt(float(np.sum(px * xs ** 2)))
    sig_ana = s0 * math.sqrt(1 + (t_end / (2 * s0 ** 2)) ** 2)
    sig_rel = abs(sig / sig_ana - 1)

    # 3) energia con pared (sin absorbente): el paquete choca y rebota
    V = np.zeros((ny, nx))
    V[100:104, :] = V_WALL
    V[100:104, 120:136] = 0.0
    psi = packet(ny, nx, 170, sx=20, sy=12)
    sim = Sim(ny, nx, V)
    e0 = sim.energy(psi)
    worst = 0.0
    for _ in range(int(200 / DT)):
        psi = sim.step(psi)
        worst = max(worst, abs(sim.energy(psi) / e0 - 1))
    print(f"[slit] norma libre: error {norm_err:.1e} | dispersion: sigma {sig:.4f} "
          f"vs {sig_ana:.4f} analitico ({sig_rel:.1e}) | energia con pared: "
          f"deriva {worst:.1e}")
    assert norm_err < 1e-12, "el paso no es unitario"
    assert sig_rel < 1e-6, "el paquete libre no se ensancha como dice la formula"
    assert worst < 5e-3, "la energia no se conserva al chocar con la pared"
    return {"norm_err": norm_err, "sigma_rel": sig_rel, "energy_drift": worst}


def fringe_check(Px):
    """maximos medidos contra la formula de Fraunhofer de dos rendijas,
    I ~ cos^2(pi d sin(theta) / lambda) sinc^2(a sin(theta) / lambda),
    fuera de la franja absorbente de los lados"""
    x = (np.arange(NX) + 0.5 - NX / 2)
    L = (Y_WALL - Y_SCREEN) * NY
    lim = NX / 2 - CAP_W

    def peaks(xs, p, thr):
        out = []
        for i in range(1, len(p) - 1):
            if p[i] >= p[i - 1] and p[i] > p[i + 1] and p[i] > thr * p.max() \
                    and abs(xs[i]) < lim:
                a, b, c = p[i - 1], p[i], p[i + 1]
                out.append(xs[i] + 0.5 * (a - c) / (a - 2 * b + c) * (xs[1] - xs[0]))
        return np.array(out)

    meas = peaks(x, gaussian_filter(Px, 1.0), 0.04)
    xf = np.linspace(-NX / 2, NX / 2, 20001)
    sn = xf / np.hypot(xf, L)
    theo = np.cos(np.pi * D * sn / LAM) ** 2 * np.sinc(A * sn / LAM) ** 2
    pred = peaks(xf, theo, 0.04)
    spacing = LAM * L / D
    pairs = [(m, pred[np.argmin(np.abs(pred - m))]) for m in meas]
    err = max(abs(m - q) for m, q in pairs) / spacing
    print(f"[slit] {len(meas)} maximos medidos en la pantalla, frente a la formula "
          f"de Fraunhofer: error max {err * 100:.1f}% de la separacion entre franjas "
          f"({spacing * SC:.0f} px) | en px: "
          + ", ".join(f"{m * SC:.0f}/{q * SC:.0f}" for m, q in pairs))
    assert len(meas) >= 5, "no aparecen las franjas"
    assert err < 0.05, f"las franjas no caen donde dice Fraunhofer ({err:.3f})"
    return [float(m * SC) for m in meas], err


def pass1():
    if os.path.isfile(CACHE):
        z = np.load(CACHE)
        return {k: z[k] for k in z.files}
    V = wall_potential(NY, NX)
    mask = absorber(NY, NX)
    sim = Sim(NY, NX, V, mask)
    psi = packet(NY, NX, Y_SRC * NY)
    ys = int(Y_SCREEN * NY)
    yw = int(Y_WALL * NY)
    Px = np.zeros(NX)
    ghost = np.zeros((NY, NX), np.float32)
    flux_t = []
    trans = 0.0
    step = 0
    while True:
        psi = sim.step(psi)
        step += 1
        jy = np.imag(np.conj(psi[ys]) * (psi[ys + 1] - psi[ys - 1]) * 0.5)
        Px += -jy * DT
        flux_t.append(float(np.sum(-jy) * DT))
        ghost += np.abs(psi) ** 2
        if step % 100 == 0:
            left = float(np.sum(np.abs(psi[ys - 4:yw]) ** 2))
            tot = float(np.sum(np.abs(psi) ** 2))
            print(f"[slit] paso {step}: entre pared y pantalla {left:.2e}, "
                  f"norma {tot:.3f}, flujo acumulado {Px.sum():.4f}")
            if step > 600 and left < 1e-4 * max(Px.sum(), 1e-9):
                break
    cum = np.cumsum(flux_t)
    n_coll = int(np.searchsorted(cum, COLLAPSE_FRAC * cum[-1]))
    out = {"Px": Px, "ghost": ghost, "cum": cum, "n_coll": np.array(n_coll),
           "steps": np.array(step)}
    os.makedirs(OUT, exist_ok=True)
    np.savez(CACHE, **out)
    return out


# ------------------------------------------------------------------ dibujo
def palette(phase):
    """paleta ciclica suave (coseno), fase -> rgb"""
    t = phase[..., None] / (2 * np.pi)
    a = np.array([0.50, 0.50, 0.55])
    b = np.array([0.50, 0.42, 0.45])
    d = np.array([0.00, 0.30, 0.62])
    return np.clip(a + b * np.cos(2 * np.pi * (t + d)), 0, 1)


def up(a):
    return zoom(a, (H / a.shape[0], W / a.shape[1]), order=1)


def wall_layer():
    img = np.zeros((H, W, 3))
    y = np.arange(H)[:, None] + 0.5
    x = np.arange(W)[None, :] + 0.5 - W / 2
    band = np.abs(y - Y_WALL * H) < WALL_PX / 2
    open_ = np.abs(np.abs(x) - D_PX / 2) < A_PX / 2
    m = (band & ~open_).astype(float)
    m = gaussian_filter(m, 0.7)
    img += m[..., None] * np.array([0.62, 0.66, 0.78])
    glow = gaussian_filter(m, 6) * 0.35
    img += glow[..., None] * np.array([0.35, 0.45, 0.8])
    return img, m


def screen_line():
    img = np.zeros((H, W, 3))
    ys = int(Y_SCREEN * H)
    img[ys - 1:ys + 2] = np.array([0.20, 0.24, 0.34])
    y0, y1 = int(Y_PLATE0 * H), int(Y_PLATE1 * H)
    img[y0:y1] += np.array([0.012, 0.014, 0.024])
    return img


def wave_rgb(psi, ref_lo, ref_hi):
    a = np.abs(psi)
    ph = np.angle(psi) % (2 * np.pi)
    yw = int(Y_WALL * NY)
    gain = np.ones(NY)
    gain[:yw] = 1 / ref_hi
    gain[yw:] = 1 / ref_lo
    v = 1 - np.exp(-1.6 * (a * gain[:, None]) ** 1.3)
    re = up(np.real(psi) * gain[:, None])
    im = up(np.imag(psi) * gain[:, None])
    vv = up(v)
    ph = np.arctan2(im, re) % (2 * np.pi)
    col = palette(ph)
    return col * vv[..., None], vv


def tone(img):
    return np.clip(1 - np.exp(-1.25 * img), 0, 1)


def save(f, img):
    if ONLY and f not in ONLY:
        return
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        os.path.join(FRAMES_DIR, f"{f + 1:04d}.png"))


def splat(acc, x, y, w):
    xi = np.floor(x).astype(int)
    yi = np.floor(y).astype(int)
    fx, fy = x - xi, y - yi
    for dx, dy, ww in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                       (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xx, yy = np.clip(xi + dx, 0, W - 1), np.clip(yi + dy, 0, H - 1)
        acc += np.bincount((yy * W + xx).ravel(), (w * ww).ravel(),
                           minlength=H * W).reshape(H, W)


def n_dots(t):
    """cuantos electrones han llegado a la placa en el segundo t"""
    t0 = T_COLLAPSE
    singles = [0.0, 0.85, 1.55, 2.15, 2.6]
    if t < t0:
        return 0
    s = t - t0
    n = sum(1 for q in singles if s >= q)
    if s <= singles[-1]:
        return n
    t_end = 13.6 - t0
    u = min(1.0, (s - singles[-1]) / (t_end - singles[-1]))
    return int(round(len(singles) * (NDOTS / len(singles)) ** (u ** 1.15)))


def main():
    os.makedirs(FRAMES_DIR, exist_ok=True)
    ver = verify()
    p1 = pass1()
    Px = np.maximum(p1["Px"], 0)
    ords, ferr = fringe_check(Px)
    n_coll = int(p1["n_coll"])
    trans = float(p1["Px"].sum())
    print(f"[slit] colapso en el paso {n_coll} de {int(p1['steps'])}, "
          f"llega a la pantalla {trans * 100:.1f}% de la probabilidad")

    # donde caen los electrones: muestreo de la P(x) medida
    rng = np.random.default_rng(SEED)
    cdf = np.cumsum(Px) / Px.sum()
    u = rng.random(NDOTS)
    xc = (np.searchsorted(cdf, u) + rng.random(NDOTS)) * SC
    yc = rng.uniform(Y_PLATE0 * H + 6, Y_PLATE1 * H - 6, NDOTS)

    wall, wall_m = wall_layer()
    base = screen_line()
    # huella: densidad de probabilidad promediada en todo el experimento.
    # Arriba de la pared en oro (lo que llega a la placa), abajo en azul (la
    # onda que llega y la que rebota)
    gy = zoom(p1["ghost"], (H / NY, W / NX), order=1)
    yw = int(Y_WALL * H)
    gy[: int(Y_SCREEN * H)] = 0
    hi, lo = gy[:yw], gy[yw:]
    hi = np.clip((hi / np.percentile(hi[hi > 0], 99.7)) ** 0.55, 0, 1.4)
    lo = np.clip((lo / np.percentile(lo[lo > 0], 99.7)) ** 0.8, 0, 1.2)
    ghost_rgb = np.concatenate([hi[..., None] * np.array([1.0, 0.72, 0.30]),
                                lo[..., None] * np.array([0.25, 0.45, 1.0]) * 0.6])
    V = wall_potential(NY, NX)
    sim = Sim(NY, NX, V, absorber(NY, NX))
    psi = packet(NY, NX, Y_SRC * NY)
    ref_lo = float(np.abs(psi).max())
    ref_hi = ref_lo * 0.22
    sim_step = 0
    coll_f = int(round(T_COLLAPSE * FPS))
    last_wave = None
    dot_x0, dot_y0 = xc[0], yc[0]
    acc = np.zeros((H, W))
    t_arr = np.full(NDOTS, -9.0)
    placed = 0
    shown = []
    for f in range(FRAMES):
        t = f / FPS
        img = base.copy()
        if f <= coll_f:
            target = int(round(n_coll * f / coll_f))
            while sim_step < target:
                psi = sim.step(psi)
                sim_step += 1
            if not ONLY or f in ONLY or f == coll_f:
                wrgb, _ = wave_rgb(psi, ref_lo, ref_hi)
                last_wave = wrgb
                img += wrgb * 1.35
        else:
            # colapso: la onda se encoge hacia el punto donde cae el electron
            s = (t - T_COLLAPSE) / 0.35
            if s < 1 and last_wave is not None:
                yy = np.arange(H)[:, None] - dot_y0
                xx = np.arange(W)[None, :] - dot_x0
                r = (1 - s) ** 2 * 1400 + 4
                m = np.exp(-(xx ** 2 + yy ** 2) / (2 * r * r)) * (1 - s) ** 1.5
                img += last_wave * 1.35 * m[..., None]
        # la huella de la onda (densidad promedio) aparece con los impactos
        nd = n_dots(t)
        if nd > placed:
            k = np.arange(placed, nd)
            wgt = np.full(len(k), 1.0)
            splat(acc, xc[k], yc[k], wgt)
            t_arr[k] = t
            placed = nd
        if placed:
            ga = min(1.0, math.log1p(placed) / math.log1p(NDOTS)) ** 2.2
            img += ghost_rgb * 0.55 * ga
            dens = gaussian_filter(acc, 0.8)
            gain_d = 6.0 / (1 + placed / 3000) ** 0.72
            dimg = 1 - np.exp(-dens * gain_d)
            img += dimg[..., None] * np.array([1.0, 0.86, 0.58]) * 1.6
            # destello de los impactos recientes: cada uno brilla al llegar
            age = t - t_arr[:placed]
            fresh = np.nonzero(age < 0.6)[0]
            if len(fresh):
                amp = np.exp(-age[fresh] * 5.0) * (1.0 if placed <= 5 else
                                                   min(1.0, 40.0 / len(fresh)))
                fl = np.zeros((H, W))
                splat(fl, xc[fresh], yc[fresh], amp)
                fl = gaussian_filter(fl, 2.5) * 25 + gaussian_filter(fl, 12) * 180
                img += fl[..., None] * np.array([1.0, 0.95, 0.85])
        img += wall
        img = tone(img)
        save(f, img)
        shown.append({"n": int(placed), "t_sim": int(min(sim_step, n_coll))})
        if f % 60 == 0:
            print(f"[slit] cuadro {f}/{FRAMES}: paso {sim_step}, electrones {placed}")

    ev = {"duration_s": FRAMES / FPS, "fps": FPS, "ndots": NDOTS,
          "lambda_px": LAM_PX, "d_px": D_PX, "a_px": A_PX,
          "L_px": (Y_WALL - Y_SCREEN) * H,
          "fringe_px": LAM_PX * (Y_WALL - Y_SCREEN) * H / D_PX,
          "fringe_err": ferr, "peaks_px": ords,
          "transmitted": trans, "collapse_s": T_COLLAPSE, "grid": [NY, NX],
          "verify": ver, "shown": shown,
          "events": [{"frame": coll_f, "note": "A4"}]}
    os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
    with open(EVENTS, "w", encoding="utf-8") as fh:
        json.dump(ev, fh)


if __name__ == "__main__":
    main()
