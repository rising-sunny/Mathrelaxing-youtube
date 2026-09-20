"""
Navier-Stokes 2-D incompresible, pseudoespectral, en vorticidad.

    d(w)/dt + u . grad(w) = nu lap(w),    lap(psi) = -w,    u = (psi_y, -psi_x)

En dos dimensiones la vorticidad es un ESCALAR que solo se transporta y se
difunde. Un escalar asi obedece el principio del maximo: su valor absoluto
maximo no puede crecer nunca. De ahi sale, en una linea, que las soluciones
2-D son suaves para siempre.

En tres dimensiones la vorticidad es un VECTOR y aparece el termino de
estiramiento (w . grad)u, que si puede amplificarla. Ese termino es la razon
de que el caso 3-D siga siendo un problema del milenio.

La escena muestra la cascada inversa: se arranca con vorticidad de escala
pequena y los remolinos se van fusionando en pocos y grandes, mientras
max|w| solo baja. Todo lo que sale en pantalla esta medido, no citado.

Uso:
    python scenes/navier_stokes.py -- --frames 900 --res 1920 --name shorts_ns
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, label

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_ns")
FPS = int(arg("--fps", 60))
NX = int(arg("--nx", 360))              # malla: el lado corto
NY = int(arg("--ny", 640))              # malla: el lado largo (9:16 exacto)
K0 = float(arg("--k0", 26.0))           # numero de onda inicial
NU = float(arg("--nu", 8.0e-4))
DT = float(arg("--dt", 0.01))
TURNS = float(arg("--turns", 20.0))     # duracion en tiempos de giro
SEED = int(arg("--seed", 7))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

W_PIX, H_PIX = int(round(RES * 9 / 16)), RES
W_PIX -= W_PIX % 2
H_PIX -= H_PIX % 2


# --------------------------------------------------------------------------
# Solver
# --------------------------------------------------------------------------
def make_grid(nx, ny):
    """Caja periodica con el mismo paso en las dos direcciones."""
    lx, ly = 2 * math.pi * nx / ny, 2 * math.pi
    kx = np.fft.rfftfreq(nx, d=lx / nx) * 2 * math.pi
    ky = np.fft.fftfreq(ny, d=ly / ny) * 2 * math.pi
    KX, KY = np.meshgrid(kx, ky)
    K2 = KX ** 2 + KY ** 2
    inv = np.where(K2 > 0, 1.0 / np.where(K2 == 0, 1.0, K2), 0.0)
    # regla de los dos tercios: el producto u*grad(w) duplica el ancho de
    # banda, y sin cortar ese tercio la energia se pliega sobre si misma
    mask = (np.abs(KX) < 2 / 3 * kx.max()) & (np.abs(KY) < 2 / 3 * np.abs(ky).max())
    return KX, KY, K2, inv, mask


def velocity(W, KX, KY, inv):
    P = W * inv                                   # funcion de corriente
    return np.fft.irfft2(1j * KY * P), np.fft.irfft2(-1j * KX * P)


def rhs(W, KX, KY, K2, inv, mask, nu):
    u, v = velocity(W, KX, KY, inv)
    wx = np.fft.irfft2(1j * KX * W)
    wy = np.fft.irfft2(1j * KY * W)
    return -np.fft.rfft2(u * wx + v * wy) * mask - nu * K2 * W


def step(W, dt, *a):
    k1 = rhs(W, *a)
    k2 = rhs(W + 0.5 * dt * k1, *a)
    k3 = rhs(W + 0.5 * dt * k2, *a)
    k4 = rhs(W + dt * k3, *a)
    return W + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)


def initial(KX, KY, K2, mask, k0, seed):
    """Fases aleatorias con el espectro concentrado en k0. Se normaliza a
    w_rms = 1, de modo que la unidad de tiempo ES el tiempo de giro."""
    rng = np.random.default_rng(seed)
    k = np.sqrt(K2)
    amp = (k ** 1.5) / (1.0 + (k / k0) ** 5.0)
    W = amp * np.exp(2j * math.pi * rng.random(K2.shape)) * mask
    W[0, 0] = 0.0
    w = np.fft.irfft2(W)
    return np.fft.rfft2((w - w.mean()) / w.std())


def energy_enstrophy(W, KX, KY, inv):
    w = np.fft.irfft2(W)
    u, v = velocity(W, KX, KY, inv)
    return 0.5 * np.mean(u * u + v * v), 0.5 * np.mean(w * w)


def count_vortices(w, rms):
    """Censo de remolinos: componentes conexas donde |w| pasa de dos veces
    la rms del instante. Es el criterio de umbral habitual; el factor 2 se
    fija una vez y no se toca durante la corrida."""
    n_pos = label(w > 2.0 * rms)[1]
    n_neg = label(w < -2.0 * rms)[1]
    return n_pos + n_neg


def spectrum(W, K2, ny):
    """E(k) integrado en cascarones de ancho 1."""
    k = np.sqrt(K2)
    kb = np.clip(np.round(k).astype(int), 0, ny)
    # rfft2: las columnas interiores representan tambien su conjugada
    wgt = np.full(W.shape, 2.0)
    wgt[:, 0] = 1.0
    if W.shape[1] * 2 - 2 == W.shape[1] * 2 - 2:
        wgt[:, -1] = 1.0
    e = 0.5 * wgt * np.abs(W) ** 2 * np.where(K2 > 0, 1.0 / np.where(K2 == 0, 1, K2), 0)
    return np.bincount(kb.ravel(), weights=e.ravel(), minlength=ny + 1)


# --------------------------------------------------------------------------
# Color: divergente y con el cero en negro, para que los remolinos brillen
# --------------------------------------------------------------------------
def make_lut(n=1024):
    """w > 0 -> ambar; w < 0 -> cian; el cero, casi negro.

    La curva es dura (a^1.35): en turbulencia 2-D casi todo
    el plano tiene vorticidad mediana, y una rampa lineal la pinta entera
    de rojo y azul. Con el medio apagado solo encienden los filamentos y
    los nucleos, que es donde esta la fisica.
    """
    t = np.linspace(-1.0, 1.0, n)
    a = np.abs(t)[:, None]
    warm = np.array([1.00, 0.44, 0.09])[None, :]
    cool = np.array([0.10, 0.72, 1.00])[None, :]
    body = (a ** 1.35) * np.where((t > 0)[:, None], warm, cool)
    veil = (a ** 3.0) * 0.26                     # halo suave alrededor del nucleo
    hot = np.clip((a - 0.74) / 0.26, 0.0, 1.0) ** 1.5
    bg = np.array([0.015, 0.021, 0.052])[None, :] * (1.0 - a)
    return np.clip(bg + body + veil + hot * np.array([1.0, 0.96, 0.88])[None, :],
                   0.0, 1.0)


LUT = make_lut()


def colorize(w, scale):
    idx = np.clip((w / scale * 0.5 + 0.5) * (len(LUT) - 1), 0, len(LUT) - 1)
    return LUT[idx.astype(np.int32)]


# --------------------------------------------------------------------------
def verify(nx=96, ny=160):
    """Validacion del solver antes de gastar una hora de render.

    Sin viscosidad, el sistema conserva energia Y enstrofia; es la prueba
    mas exigente que se le puede pedir a un esquema pseudoespectral, porque
    cualquier error de aliasing rompe la segunda antes que la primera.
    """
    KX, KY, K2, inv, mask = make_grid(nx, ny)
    W = initial(KX, KY, K2, mask, 8.0, 3)
    E0, Z0 = energy_enstrophy(W, KX, KY, inv)
    for _ in range(400):
        W = step(W, 0.01, KX, KY, K2, inv, mask, 0.0)
    E1, Z1 = energy_enstrophy(W, KX, KY, inv)
    dE, dZ = abs(E1 / E0 - 1), abs(Z1 / Z0 - 1)
    u, v = velocity(W, KX, KY, inv)
    div = np.abs(np.fft.irfft2(1j * KX * np.fft.rfft2(u)
                               + 1j * KY * np.fft.rfft2(v))).max()
    print(f"[ns] sin viscosidad, 400 pasos: energia deriva {dE*100:.5f}%, "
          f"enstrofia {dZ*100:.5f}%, max|div u| {div:.1e}")
    assert dE < 1e-4, f"la energia deriva {dE*100:.4f}%: el solver no sirve"
    assert dZ < 1e-4, f"la enstrofia deriva {dZ*100:.4f}%: hay aliasing"
    assert div < 1e-10, f"el campo no es solenoidal: max|div u| = {div:.1e}"
    return dE, dZ, div


def main():
    dE, dZ, div = verify()

    KX, KY, K2, inv, mask = make_grid(NX, NY)
    W = initial(KX, KY, K2, mask, K0, SEED)
    w = np.fft.irfft2(W)
    w_max0 = float(np.abs(w).max())
    E0, Z0 = energy_enstrophy(W, KX, KY, inv)
    print(f"[ns] malla {NX}x{NY}, nu={NU:.1e}, k0={K0:.0f}, "
          f"{TURNS:.0f} tiempos de giro en {FRAMES/FPS:.0f} s de clip")

    dt_frame = TURNS / FRAMES
    nsub = max(1, int(math.ceil(dt_frame / DT)))
    dt = dt_frame / nsub
    print(f"[ns] dt={dt:.5f}, {nsub} subpasos por cuadro, "
          f"{nsub*FRAMES} pasos en total")

    # La escala de color sigue a la rms del instante (3 sigma). Con escala
    # fija el cuadro se apaga hasta quedar negro y no se ve la unica cosa
    # interesante del final, que es la forma de los remolinos. La caida de
    # max|w| NO se esconde por eso: sale escrita en pantalla, cuadro a
    # cuadro, en valor absoluto.
    peak = w_max0
    tm, tmax, tvor, tE, tZ = [], [], [], [], []
    scale_note = ["D2", "A2", "D3", "F3", "A3", "C4", "E4", "G4"]
    events = []

    for f in range(FRAMES):
        w = np.fft.irfft2(W)
        wm = float(np.abs(w).max())
        peak = max(peak, wm)
        assert wm <= w_max0 * 1.002, (
            f"max|w| subio a {wm:.4f} desde {w_max0:.4f} en el cuadro {f}: "
            "eso violaria el principio del maximo")
        rms = float(w.std())
        nv = count_vortices(w, rms)
        E, Z = energy_enstrophy(W, KX, KY, inv)
        tm.append(f * dt_frame); tmax.append(wm); tvor.append(nv)
        tE.append(E / E0); tZ.append(Z / Z0)

        rgb = colorize(w, 3.0 * rms)
        img = Image.fromarray((rgb * 255).astype(np.uint8), "RGB")
        img = img.resize((W_PIX, H_PIX), Image.BICUBIC)
        a = np.asarray(img).astype(np.float32) / 255.0
        a = np.clip(a + 0.42 * gaussian_filter(a, (2.6, 2.6, 0)), 0.0, 1.0)
        Image.fromarray((a * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[ns] {f+1}/{FRAMES}  t={f*dt_frame:5.2f}  max|w| {wm:.4f}"
                  f"  remolinos {nv:4d}  E {E/E0*100:5.1f}%  Z {Z/Z0*100:5.1f}%")

        for _ in range(nsub):
            W = step(W, dt, KX, KY, K2, inv, mask, NU)

    # --- la pendiente del espectro al final ---------------------------------
    Ek = spectrum(W, K2, NY)
    # la caja es mas corta en x, asi que kx y ky llegan los dos hasta NY/2;
    # tras el corte de los dos tercios el limite util es 2/3 de eso
    kcut = (2.0 / 3.0) * NY / 2.0
    lo, hi = int(2.5 * K0), int(0.62 * kcut)
    ks = np.arange(lo, hi)
    good = Ek[lo:hi] > 0
    slope, _ = np.polyfit(np.log(ks[good]), np.log(Ek[lo:hi][good]), 1)
    print(f"[ns] pendiente de E(k) entre k={lo} y k={hi}: {slope:.2f}")

    print(f"[ns] max|w| {w_max0:.4f} -> {tmax[-1]:.4f}   pico de toda la "
          f"corrida {peak:.4f}  (principio del maximo: OK)")
    print(f"[ns] remolinos {tvor[0]} -> {tvor[-1]}")
    print(f"[ns] queda {tE[-1]*100:.1f}% de la energia y {tZ[-1]*100:.1f}% "
          "de la enstrofia")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "nx": NX, "ny": NY, "nu": NU, "k0": K0, "turns": TURNS,
                   "t": tm, "wmax": tmax, "vortices": tvor,
                   "energy_frac": tE, "enstrophy_frac": tZ,
                   "wmax0": w_max0, "peak_wmax": peak,
                   "slope": float(slope), "slope_lo": lo, "slope_hi": hi,
                   "drift_energy": dE, "drift_enstrophy": dZ, "max_div": div},
                  jf)
    print(f"[ns] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
