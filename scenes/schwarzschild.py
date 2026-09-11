"""Geodesicas de Schwarzschild: particulas cayendo por la curvatura.

En Newton una particula ligada recorre una elipse que se cierra. En
relatividad general no: la ecuacion radial de una geodesica temporal en el
plano ecuatorial de Schwarzschild (G = c = 1, masa M) es

    d2r/dtau2 = -M/r^2 + L^2/r^3 - 3 M L^2 / r^4

Los dos primeros terminos son exactamente Newton -- gravedad mas fuerza
centrifuga. El tercero no existe en Newton: sale de la curvatura del
espacio-tiempo, y es el que hace que la orbita no cierre. Cada vuelta el
perihelio se corre y la trayectoria dibuja una roseta. Es el mismo termino que
explica los 43 segundos de arco por siglo de Mercurio.

Tambien fija dos radios que Newton no tiene:
  r = 6M  ultima orbita circular estable (ISCO); mas adentro no hay ninguna
  r = 3M  esfera de fotones, donde la luz puede orbitar
Una particula que cruza r = 3M hacia adentro esta capturada: el maximo del
potencial efectivo esta siempre en r >= 3M, asi que ya no puede volver.

La integracion va en tiempo COORDENADO t, el de un observador lejano, con
dt/dtau = E/(1-2M/r). Por eso lo que se ve al final es lo que se veria de
verdad: nada cruza el horizonte, las particulas se frenan y se apagan en el
borde. El brillo lleva el factor (1-2M/r) del corrimiento al rojo.

    python scenes/schwarzschild.py -- --frames 900 --res 1920 --name shorts_schwarzschild --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_schwarzschild")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
N = int(arg("--n", 420))
HALF_H = float(arg("--half-h", 16.0))   # media altura del cuadro, en unidades M
DT = float(arg("--dt", 0.18))           # paso de tiempo coordenado
SUB = int(arg("--sub", 10))             # subpasos por frame (traza continua)
GAIN = float(arg("--gain", 3.4))        # brillo global de las trazas
SEED = int(arg("--seed", 7))

M = 1.0
R_HOR = 2.0 * M
R_PHOTON = 3.0 * M
R_ISCO = 6.0 * M

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

PPU = H / (2.0 * HALF_H)                # pixeles por unidad M
CX, CY = W / 2.0, H / 2.0
# Una traza es una curva 1-D: a mas resolucion el mismo tramo cubre mas
# pixeles y el deposito por pixel cae como 1/PPU. Sin este factor la escena se
# ve bien al previsualizarla chica y sale casi negra a 1080x1920.
GAIN *= PPU / 25.0

HOT = np.array([1.00, 0.66, 0.20])      # poco momento angular: orbita apretada
COLD = np.array([0.32, 0.80, 1.00])     # mucho: orbita ancha
L_LO, L_HI = 3.40, 4.05                 # rango de L para el mapa de color

rng = np.random.default_rng(SEED)


def v_eff(r, L):
    """Potencial efectivo (1-2M/r)(1+L^2/r^2); E^2 = u^2 + V."""
    return (1.0 - 2.0 * M / r) * (1.0 + L * L / (r * r))


def r_circ(L):
    """Radio de la orbita circular ESTABLE para un L dado (requiere L^2 > 12M^2)."""
    return (L * L + L * np.sqrt(np.maximum(L * L - 12.0 * M * M, 0.0))) / (2.0 * M)


def spawn(n):
    """Tres poblaciones: rosetas ligadas, orbitas zoom-whirl y caidas directas."""
    kind = rng.random(n)
    r = np.empty(n)
    u = np.zeros(n)
    L = np.empty(n)

    # 1) Ligadas: se arranca en el apoastro de una orbita de excentricidad e.
    #    Como r0 > r_circ y u = 0, la particula queda atrapada en el pozo y
    #    nunca cae: son las rosetas que llenan el cuadro.
    a = kind < 0.66
    na = int(a.sum())
    rc = rng.uniform(6.1, 11.5, na)
    L[a] = np.sqrt(M * rc * rc / (rc - 3.0 * M))
    r[a] = rc * (1.0 + rng.uniform(0.05, 0.45, na))

    # 2) Zoom-whirl: L apenas arriba de 2*sqrt(3)M, entrando desde lejos. Dan
    #    varias vueltas pegadas al agujero y vuelven a salir, o caen.
    b = (kind >= 0.66) & (kind < 0.88)
    nb = int(b.sum())
    L[b] = rng.uniform(3.47, 3.78, nb)
    r[b] = rng.uniform(14.0, 17.0, nb)
    u[b] = -rng.uniform(0.030, 0.085, nb)

    # 3) Caidas: L por debajo del limite, no hay barrera que las detenga.
    c = kind >= 0.88
    nc = int(c.sum())
    L[c] = rng.uniform(1.1, 3.40, nc)
    r[c] = rng.uniform(12.0, 17.0, nc)
    u[c] = -rng.uniform(0.02, 0.10, nc)

    phi = rng.uniform(0.0, 2.0 * np.pi, n)
    E = np.sqrt(np.maximum(u * u + v_eff(r, L), 1e-6))
    # El color queda FIJO por particula, mapeado desde su L: asi cada roseta es
    # de un solo color y se puede seguir entre todas las demas.
    q = np.clip((L - L_LO) / (L_HI - L_LO), 0.0, 1.0)[:, None]
    col = HOT * (1.0 - q) + COLD * q
    return r, u, phi, L, E, col


def deriv(r, u, L, E):
    """Geodesica temporal, reparametrizada a tiempo coordenado t."""
    f = 1.0 - 2.0 * M / r
    k = f / E
    dr = u * k
    du = (-M / r ** 2 + L ** 2 / r ** 3 - 3.0 * M * L ** 2 / r ** 4) * k
    dphi = L / (r * r) * k
    return dr, du, dphi


def rk4(r, u, phi, L, E, h):
    k1r, k1u, k1p = deriv(r, u, L, E)
    k2r, k2u, k2p = deriv(r + 0.5 * h * k1r, u + 0.5 * h * k1u, L, E)
    k3r, k3u, k3p = deriv(r + 0.5 * h * k2r, u + 0.5 * h * k2u, L, E)
    k4r, k4u, k4p = deriv(r + h * k3r, u + h * k3u, L, E)
    r = r + h / 6.0 * (k1r + 2 * k2r + 2 * k3r + k4r)
    u = u + h / 6.0 * (k1u + 2 * k2u + 2 * k3u + k4u)
    phi = phi + h / 6.0 * (k1p + 2 * k2p + 2 * k3p + k4p)
    return np.maximum(r, 2.0 * M + 1e-4), u, phi


def splat(acc, x, y, w):
    """Acumulacion bilineal en 3 canales con bincount (np.add.at es 10x mas lento)."""
    ok = (x >= 0) & (x < W - 1) & (y >= 0) & (y < H - 1)
    if not ok.any():
        return
    x, y, w = x[ok], y[ok], w[ok]
    ix, iy = x.astype(np.int64), y.astype(np.int64)
    fx, fy = x - ix, y - iy
    base = iy * W + ix
    flat = acc.reshape(-1, 3)
    for off, wt in ((0, (1 - fx) * (1 - fy)), (1, fx * (1 - fy)),
                    (W, (1 - fx) * fy), (W + 1, fx * fy)):
        idx = base + off
        for ch in range(3):
            flat[:, ch] += np.bincount(idx, weights=wt * w[:, ch],
                                       minlength=flat.shape[0])


def ring_mask(radius, width):
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - CX) / PPU) ** 2 + ((yy - CY) / PPU) ** 2)
    return np.exp(-((d - radius) / width) ** 2)


def main():
    r, u, phi, L, E, pcol = spawn(N)
    captured = np.zeros(N, dtype=bool)     # cruzo r = 3M hacia adentro
    n_captured = 0

    trail = np.zeros((H, W, 3), dtype=np.float32)
    paint = np.zeros((H, W, 3), dtype=np.float32)

    photon = (ring_mask(R_PHOTON, 0.085)[..., None]
              * np.array([0.85, 0.90, 1.0], dtype=np.float32) * 0.20)
    isco = (ring_mask(R_ISCO, 0.075)[..., None]
            * np.array([1.0, 0.80, 0.34], dtype=np.float32) * 0.17)
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - CX) / PPU) ** 2 + ((yy - CY) / PPU) ** 2)
    # borde suavizado: un disco duro deja escalones visibles en el horizonte
    hole = np.clip((R_HOR - dist) * PPU / 1.2 + 0.5, 0.0, 1.0)[..., None].astype(np.float32)
    rim = (np.exp(-((dist - R_HOR) / 0.30) ** 2) * (dist >= R_HOR))[..., None] \
        * np.array([1.0, 0.62, 0.22], dtype=np.float32) * 0.34

    scale_note = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3"]
    events = []
    captures_per_frame = []

    def draw(r, phi, w):
        f_red = np.clip(1.0 - 2.0 * M / r, 0.0, 1.0)       # corrimiento al rojo
        x = CX + r * np.cos(phi) * PPU
        y = CY + r * np.sin(phi) * PPU
        col = (pcol * f_red[:, None] * w).astype(np.float32)
        splat(trail, x, y, col)
        splat(paint, x, y, col * 0.46)

    for f in range(FRAMES):
        trail *= 0.93
        paint *= 0.982
        # La traza se dibuja en CADA subpaso, con un degradado suave dentro del
        # frame. Un splat extra de "cabeza" una vez por frame dejaba una cuenta
        # brillante cada ~14 px y la curva parecia un collar.
        for i in range(SUB):
            r, u, phi = rk4(r, u, phi, L, E, DT)
            draw(r, phi, (0.45 + 1.15 * i / (SUB - 1)) / SUB)

        newly = (~captured) & (r < R_PHOTON) & (u < 0.0)
        n_new = int(newly.sum())
        if n_new:
            captured |= newly
            n_captured += n_new
        captures_per_frame.append(n_captured)

        # Ya invisibles por el corrimiento al rojo: se reciclan lejos para que
        # la densidad no se vaya cayendo a lo largo del clip.
        dead = r < 2.0 * M + 0.02
        nd = int(dead.sum())
        if nd:
            r2, u2, p2, L2, E2, c2 = spawn(nd)
            r[dead], u[dead], phi[dead] = r2, u2, p2
            L[dead], E[dead], pcol[dead] = L2, E2, c2
            captured[dead] = False

        img = (trail * 2.60 + paint * 1.05) * GAIN
        img = img + photon + isco + rim
        img = 1.0 - np.exp(-2.05 * np.maximum(img, 0.0))     # tono filmico
        img = np.clip(img + 0.40 * gaussian_filter(img, (1.5, 1.5, 0)), 0.0, 1.0)
        img *= (1.0 - hole)                                  # el horizonte es negro
        Image.fromarray((img * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[schw] {f + 1}/{FRAMES}  capturadas {n_captured}  "
                  f"r medio {r.mean():.2f}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "captured": captures_per_frame}, jf)
    print(f"[schw] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
