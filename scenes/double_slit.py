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
NDOTS = int(arg("--ndots", 20000))       # por acto

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

COLLAPSE_FRAC = 0.40                        # fraccion del flujo que ya llego

# guion, en segundos, sobre los tiempos de la musica (16 tiempos en 15 s)
T1 = 3.75                                   # colapso del primer electron (tiempo 4)
T_STOP2 = 7.5                               # ultima salida de la primera lluvia
T_DROP = 8.9                                # silencio antes del giro
T_TWIST = 9.375                             # se encienden los detectores (tiempo 10)
T_STOP3 = 13.0
FLIGHT = 1.4                                # vuelo de cada electron en camara rapida
GOLD, GOLD_DOT = [1.0, 0.72, 0.30], [1.0, 0.86, 0.58]
CYAN, CYAN_DOT = [0.40, 0.78, 1.0], [0.62, 0.92, 1.0]
RED = [1.0, 0.30, 0.50]

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


def wall_potential(ny, nx, which="both"):
    y = np.arange(ny)[:, None] + 0.5
    x = np.arange(nx)[None, :] + 0.5 - nx / 2
    yw = Y_WALL * ny
    band = np.abs(y - yw) < (WALL_PX / SC) / 2
    open_ = (np.abs(np.abs(x) - D / 2) < A / 2)
    if which == "left":
        open_ = open_ & (x < 0)
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


def run_config(which, n_snap):
    """Simula un electron con las dos rendijas ("both") o solo la izquierda
    ("left"). Devuelve el flujo medido en la pantalla, la densidad promediada
    y n_snap fotos de psi repartidas hasta el colapso."""
    V = wall_potential(NY, NX, which)
    sim = Sim(NY, NX, V, absorber(NY, NX))
    psi = packet(NY, NX, Y_SRC * NY)
    ys = int(Y_SCREEN * NY)
    yw = int(Y_WALL * NY)
    Px = np.zeros(NX)
    ghost = np.zeros((NY, NX), np.float32)
    flux_t, above = [], []
    step = 0
    while True:
        psi = sim.step(psi)
        step += 1
        jy = np.imag(np.conj(psi[ys]) * (psi[ys + 1] - psi[ys - 1]) * 0.5)
        Px += -jy * DT
        flux_t.append(float(np.sum(-jy) * DT))
        ghost += np.abs(psi) ** 2
        above.append(float(np.sum(np.abs(psi[:yw - 4]) ** 2)))
        if step % 500 == 0:
            left = float(np.sum(np.abs(psi[ys - 4:yw]) ** 2))
            print(f"[slit] {which}: paso {step}, flujo acumulado {Px.sum():.4f}")
            if step > 600 and left < 1e-4 * max(Px.sum(), 1e-9):
                break
    cum = np.cumsum(flux_t)
    n_coll = int(np.searchsorted(cum, COLLAPSE_FRAC * cum[-1]))
    # cuando la onda cruza la pared: la mitad de lo que pasara ya esta arriba
    ab = np.array(above)
    n_slit = int(np.searchsorted(ab, 0.5 * ab[:n_coll].max()))
    # fotos equiespaciadas hasta el colapso: se re-simula con el mismo
    # integrador, sale identico y no hace falta guardar miles de pasos
    snaps = []
    targets = np.round(np.linspace(0, n_coll, n_snap)).astype(int)
    psi = packet(NY, NX, Y_SRC * NY)
    k = 0
    for tg in targets:
        while k < tg:
            psi = sim.step(psi)
            k += 1
        snaps.append(psi.astype(np.complex64))
    return {"Px": Px, "ghost": ghost, "n_coll": n_coll, "n_slit": n_slit,
            "steps": step, "snaps": np.array(snaps)}


def pass1(n_snap):
    if os.path.isfile(CACHE):
        z = np.load(CACHE)
        out = {k: z[k] for k in z.files}
        out["snaps_both"] = np.load(CACHE.replace(".npz", "_both.npy"), mmap_mode="r")
        out["snaps_left"] = np.load(CACHE.replace(".npz", "_left.npy"), mmap_mode="r")
        return out
    b = run_config("both", n_snap)
    l = run_config("left", n_snap)
    out = {"Px": b["Px"], "ghost": b["ghost"], "n_coll": np.array(b["n_coll"]),
           "n_slit": np.array(b["n_slit"]), "steps": np.array(b["steps"]),
           "PxL": l["Px"], "ghostL": l["ghost"], "n_collL": np.array(l["n_coll"])}
    os.makedirs(OUT, exist_ok=True)
    np.savez(CACHE, **out)
    np.save(CACHE.replace(".npz", "_both.npy"), b["snaps"])
    # la izquierda solo se usa en la lluvia: a media resolucion basta
    np.save(CACHE.replace(".npz", "_left.npy"), l["snaps"][:, ::2, ::2])
    return pass1(n_snap)


def visibility(P):
    """contraste de franjas en el centro: maximo central contra el minimo
    mas cercano (donde caen los primeros ceros de dos rendijas)"""
    x = (np.arange(NX) + 0.5 - NX / 2) * SC
    L = (Y_WALL - Y_SCREEN) * H
    x1 = 0.5 * LAM_PX * L / D_PX                  # primer minimo de Fraunhofer
    p = gaussian_filter(P, 1.0)
    c = p[np.abs(x) < 6].mean()
    m = p[np.abs(np.abs(x) - x1) < 6].mean()
    return (c - m) / (c + m)


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


def smoothstep(a, b, x):
    u = min(1.0, max(0.0, (x - a) / (b - a)))
    return u * u * (3 - 2 * u)


def wave_small(psi, ref_lo, ref_hi):
    """color de fase y brillo de |psi| a la resolucion de la foto"""
    ny = psi.shape[0]
    yw = int(Y_WALL * ny)
    gain = np.empty(ny)
    gain[:yw] = 1 / ref_hi
    gain[yw:] = 1 / ref_lo
    a = np.abs(psi) * gain[:, None]
    v = 1 - np.exp(-1.6 * a ** 1.3)
    return palette(np.angle(psi) % (2 * np.pi)) * v[..., None]


def emissions(t0, t1, r0, tau, rmax):
    """instantes de salida de los electrones: ritmo que crece exponencial"""
    out, t = [], t0
    while t < t1:
        out.append(t)
        t += 1.0 / min(rmax, r0 * math.exp((t - t0) / tau))
    return np.array(out)


def fast_forward(t, n0, n1, ta, tb):
    """camara rapida: de n0 a n1 impactos entre ta y tb"""
    if t < ta:
        return 0
    u = min(1.0, (t - ta) / (tb - ta))
    return int(round(n0 * (n1 / n0) ** (u ** 1.3)))


def curve_layer(xs, h, y_base, height):
    """linea fina con brillo: puntos cada medio pixel repartidos bilineal"""
    lay = np.zeros((H, W))
    xf = np.arange(0, W - 1, 0.5)
    yf = y_base - np.interp(xf, xs, h) * height
    splat(lay, xf, yf, np.full(len(xf), 0.5))
    return gaussian_filter(lay, 0.6) * 2.2 + gaussian_filter(lay, 4.0) * 3.0


def main():
    os.makedirs(FRAMES_DIR, exist_ok=True)
    ver = verify()
    n_snap = int(round(T1 * FPS)) + 1
    p1 = pass1(n_snap)
    Px = np.maximum(p1["Px"], 0)
    PL = np.maximum(p1["PxL"], 0)
    PW = PL + PL[::-1]                       # con detector: suma sin interferencia
    ords, ferr = fringe_check(Px)
    v2, vw = visibility(Px), visibility(PW)
    print(f"[slit] contraste de franjas: dos rendijas {v2:.3f} | mirando por cual "
          f"pasa {vw:.3f}")
    assert v2 > 0.9, "sin detector deberia haber franjas casi perfectas"
    assert vw < 0.1, "con detector las franjas tendrian que desaparecer"
    n_coll = int(p1["n_coll"])
    trans = float(Px.sum())
    transL = float(PL.sum())
    t_slit = float(p1["n_slit"]) / n_coll          # fraccion del vuelo al cruzar
    print(f"[slit] colapso en el paso {n_coll}; pasa por las dos {trans * 100:.1f}%, "
          f"por una sola {transL * 100:.1f}%; cruza la pared al {t_slit * 100:.0f}% "
          f"del vuelo")

    rng = np.random.default_rng(SEED)

    def sample(P, n):
        cdf = np.cumsum(P) / P.sum()
        return (np.searchsorted(cdf, rng.random(n)) + rng.random(n)) * SC

    y0p, y1p = Y_PLATE0 * H + 6, Y_PLATE1 * H - 6
    x2 = sample(Px, NDOTS)
    y2 = rng.uniform(y0p, y1p, NDOTS)
    side3 = rng.random(NDOTS) < 0.5                 # True: izquierda
    x3 = np.where(side3, sample(PL, NDOTS), W - sample(PL, NDOTS))
    y3 = rng.uniform(y0p, y1p, NDOTS)

    # electrones visibles: el primero (acto 1) y las dos lluvias
    em2 = emissions(T1, T_STOP2, 1.3, 1.1, 40.0)
    em3 = emissions(T_TWIST, T_STOP3, 6.0, 1.3, 45.0)
    arr2 = np.concatenate([[T1], em2 + FLIGHT])     # llegadas a la placa
    arr3 = em3 + FLIGHT
    n2v, n3v = len(arr2), len(arr3)
    print(f"[slit] ondas visibles: {n2v} sin detector, {n3v} con detector")

    wall, _ = wall_layer()
    base = screen_line()
    yw = int(Y_WALL * H)

    def ghost_img(g, col_hi):
        gy = zoom(g, (H / NY, W / NX), order=1)
        gy[: int(Y_SCREEN * H)] = 0
        hi, lo = gy[:yw], gy[yw:]
        hi = np.clip((hi / np.percentile(hi[hi > 0], 99.7)) ** 0.55, 0, 1.4)
        lo = np.clip((lo / np.percentile(lo[lo > 0], 99.7)) ** 0.8, 0, 1.2)
        return np.concatenate([hi[..., None] * np.array(col_hi),
                               lo[..., None] * np.array([0.25, 0.45, 1.0]) * 0.6])

    ghost2 = ghost_img(p1["ghost"], GOLD)
    ghost3 = ghost_img(p1["ghostL"] + p1["ghostL"][:, ::-1], CYAN)

    snaps = p1["snaps_both"]
    both_lo = np.ascontiguousarray(snaps[:, ::2, ::2])
    left_lo = np.asarray(p1["snaps_left"])
    ref_lo = float(np.abs(snaps[0]).max())
    ref_hi = ref_lo * 0.22
    last_wave = None

    # detectores sobre cada rendija
    yy, xx = np.mgrid[0:H, 0:W]
    y_det = Y_WALL * H - 30
    rings = []
    for sx in (-1, 1):
        r = np.hypot(xx - (W / 2 + sx * D_PX / 2), yy - y_det)
        ring = np.exp(-((r - 12) / 2.2) ** 2) + 0.5 * np.exp(-(r / 5) ** 2)
        rings.append(ring + gaussian_filter(ring, 10) * 4)

    # histograma: cuentas por tira de 4 px, escala comun (el pico sin detector = 1)
    bw = 4
    nb = W // bw
    xb = (np.arange(nb) + 0.5) * bw

    def binned(P):
        xs = (np.arange(NX) + 0.5) * SC
        return np.bincount(np.minimum((xs / bw).astype(int), nb - 1), P, nb)

    pk = binned(Px / Px.sum()).max()

    acc2 = np.zeros((H, W))
    acc3 = np.zeros((H, W))
    t2 = np.full(NDOTS, -9.0)
    t3 = np.full(NDOTS, -9.0)
    placed2 = placed3 = 0
    shown = []
    for f in range(FRAMES):
        t = f / FPS
        img = base.copy()
        # ---- acto 1: el primer electron, a resolucion completa
        if t < T1:
            last_wave, _ = wave_rgb(np.asarray(snaps[f]), ref_lo, ref_hi)
            img += last_wave * 1.35
        elif t < T1 + 0.35 and last_wave is not None:
            s_ = (t - T1) / 0.35
            r = (1 - s_) ** 2 * 1400 + 4
            m = np.exp(-((xx - x2[0]) ** 2 + (yy - y2[0]) ** 2) / (2 * r * r)) * (1 - s_) ** 1.5
            img += last_wave * 1.35 * m[..., None]

        # ---- las lluvias: cada onda es un electron distinto, a media resolucion
        live = []
        for i, e in enumerate(em2):
            a = t - e
            if 0 <= a < FLIGHT + 0.2:
                live.append((a, "both", i + 1, 2))
        for i, e in enumerate(em3):
            a = t - e
            if 0 <= a < FLIGHT + 0.2:
                live.append((a, "L" if side3[i] else "R", i, 3))
        if live:
            n_act = sum(1 for a, *_ in live if a < FLIGHT)
            wgt = 1.0 / (1 + n_act / 5.0) ** 0.6
            acc_w = np.zeros((NY // 2, NX // 2, 3))
            for a, side, k, act in live:
                idx = min(n_snap - 1, int(round(min(a, FLIGHT) / FLIGHT * (n_snap - 1))))
                if side == "both":
                    ps = both_lo[idx]
                elif side == "L":
                    ps = left_lo[idx]
                else:
                    ps = left_lo[idx][:, ::-1]
                rgb = wave_small(ps, ref_lo, ref_hi)
                g = wgt * min(1.0, a / 0.12)
                if a >= FLIGHT:                   # colapso hacia su punto
                    s_ = (a - FLIGHT) / 0.2
                    dx, dy = (x2[k], y2[k]) if act == 2 else (x3[k], y3[k])
                    r = (1 - s_) ** 2 * 450 + 2
                    ly, lx = np.mgrid[0:NY // 2, 0:NX // 2]
                    m = np.exp(-((lx - dx / 3) ** 2 + (ly - dy / 3) ** 2) / (2 * r * r))
                    rgb = rgb * (m * (1 - s_) ** 1.5)[..., None]
                acc_w += rgb * g
            img += np.stack([zoom(acc_w[..., c], 3, order=1) for c in range(3)], -1) * 1.35

        # ---- impactos
        n2 = min(NDOTS, max(int(np.sum(arr2 <= t)), fast_forward(t, n2v, NDOTS, 7.0, 8.75)))
        n3 = min(NDOTS, max(int(np.sum(arr3 <= t)), fast_forward(t, n3v, NDOTS, 12.2, 14.2)))
        if n2 > placed2:
            k = np.arange(placed2, n2)
            splat(acc2, x2[k], y2[k], np.ones(len(k)))
            t2[k] = t
            placed2 = n2
        if n3 > placed3:
            k = np.arange(placed3, n3)
            splat(acc3, x3[k], y3[k], np.ones(len(k)))
            t3[k] = t
            placed3 = n3

        # huellas: la densidad promedio aparece cuando la lluvia se vuelve densa
        g2 = 0.55 * smoothstep(5.6, 8.6, t) * (1 - 0.85 * smoothstep(T_TWIST, T_TWIST + 1.0, t))
        g3 = 0.55 * smoothstep(T_TWIST + 1.0, 13.4, t)
        if g2 > 0:
            img += ghost2 * g2
        if g3 > 0:
            img += ghost3 * g3

        dim2 = 1 - 0.72 * smoothstep(T_DROP, T_TWIST, t)
        for acc, placed, col, dim, tt_, xs_, ys_ in (
                (acc2, placed2, GOLD_DOT, dim2, t2, x2, y2),
                (acc3, placed3, CYAN_DOT, 1.0, t3, x3, y3)):
            if not placed:
                continue
            dens = gaussian_filter(acc, 0.8)
            gain_d = 6.0 / (1 + placed / 2500) ** 0.72
            img += (1 - np.exp(-dens * gain_d))[..., None] * np.array(col) * 1.6 * dim
            age = t - tt_[:placed]
            fresh = np.nonzero(age < 0.6)[0]
            if len(fresh):
                amp = np.exp(-age[fresh] * 5.0) * min(1.0, 30.0 / len(fresh))
                fl = np.zeros((H, W))
                splat(fl, xs_[fresh], ys_[fresh], amp)
                fl = gaussian_filter(fl, 2.5) * 25 + gaussian_filter(fl, 12) * 180
                img += fl[..., None] * np.array([1.0, 0.95, 0.85])

        # histogramas medidos sobre la placa, en escala comun
        for placed, xs_, col, dim in ((placed2, x2, GOLD_DOT, dim2 ** 0.5),
                                      (placed3, x3, CYAN_DOT, 1.0)):
            if placed < 25:
                continue
            h = np.bincount(np.minimum((xs_[:placed] / bw).astype(int), nb - 1),
                            minlength=nb) / (placed * pk)
            h = gaussian_filter(h, 1.2)
            al = min(1.0, math.log10(placed / 25) / 1.6) * dim
            img += curve_layer(xb, h, y1p + 2, 0.105 * H)[..., None] * np.array(col) * al

        # detectores: se encienden en el giro y destellan cuando pasa su electron
        if t >= T_TWIST - 0.3:
            on = smoothstep(T_TWIST - 0.3, T_TWIST, t)
            boom = math.exp(-max(0.0, t - T_TWIST) * 3.0) * 2.5
            for j, ring in enumerate(rings):
                want_left = j == 0
                fl = sum(math.exp(-abs(t - (e + t_slit * FLIGHT)) * 9.0)
                         for i, e in enumerate(em3)
                         if side3[i] == want_left and abs(t - (e + t_slit * FLIGHT)) < 0.5)
                img += ring[..., None] * np.array(RED) * (0.45 * on + boom + 1.4 * min(fl, 1.5))

        img += wall
        img = tone(img)
        save(f, img)
        shown.append({"n2": int(placed2), "n3": int(placed3)})
        if f % 60 == 0:
            print(f"[slit] cuadro {f}/{FRAMES}: ondas en vuelo {len(live)}, "
                  f"impactos {placed2} + {placed3}")

    ev = {"duration_s": FRAMES / FPS, "fps": FPS, "ndots": NDOTS,
          "lambda_px": LAM_PX, "d_px": D_PX, "a_px": A_PX,
          "L_px": (Y_WALL - Y_SCREEN) * H,
          "fringe_px": LAM_PX * (Y_WALL - Y_SCREEN) * H / D_PX,
          "fringe_err": ferr, "peaks_px": ords,
          "visibility_both": v2, "visibility_watched": vw,
          "transmitted": trans, "transmitted_one": transL,
          "t1": T1, "t_drop": T_DROP, "t_twist": T_TWIST,
          "waves_visible": [n2v, n3v], "grid": [NY, NX],
          "verify": ver, "shown": shown,
          "events": [{"frame": int(round(T1 * FPS)), "note": "A4"},
                     {"frame": int(round(T_TWIST * FPS)), "note": "A4"}]}
    os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
    with open(EVENTS, "w", encoding="utf-8") as fh:
        json.dump(ev, fh)


if __name__ == "__main__":
    main()
