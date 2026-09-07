"""Teselado hiperbolico {p,q} en el disco de Poincare — numpy puro.

Infinitos poligonos regulares, TODOS del mismo tamano. Se ven encogerse hacia
el borde porque el disco es un mapa plano de un espacio curvo: la metrica
hiperbolica 2/(1-|z|^2) diverge en el borde, asi que lo que parece un anillo de
astillas son piezas identicas a las del centro.

El teselado se dibuja por plegado inverso, no generando piezas: cada pixel se
refleja repetidamente hasta caer en el triangulo fundamental, y ahi se mide su
distancia a los tres espejos. Sale el teselado entero, con detalle infinito
hacia el borde, sin enumerar nada.

El triangulo fundamental tiene angulos pi/p (en el origen), pi/2 y pi/q, y esta
limitado por dos rectas por el origen y una circunferencia ortogonal al disco.
Con cosh(AB) = cos(pi/q)/sin(pi/p) sale el punto medio de la arista, y de ahi
el centro y el radio del espejo circular.

El movimiento es una rotacion hiperbolica de 2*pi alrededor de un punto fuera
del centro: exacta al cerrar, y mucho mas viva que un giro centrado porque
arrastra el teselado entero de un lado del disco al otro.

    python scenes/hyperbolic_tiling.py -- --frames 900 --res 1920 --name shorts_hyperbolic --format 9:16
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
NAME = arg("--name", "shorts_hyperbolic")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
P = int(arg("--p", 3))                  # lados del poligono
Q = int(arg("--q", 7))                  # poligonos por vertice
ITERS = int(arg("--iters", 16))         # profundidad del plegado
SS = int(arg("--ss", 1))                # supermuestreo (el campo de distancias ya antialiasa)
PIVOT = float(arg("--pivot", 0.38))     # centro de giro, fuera del origen
FILL = float(arg("--fill", 0.485))      # radio del disco en fraccion del ancho
EDGE = float(arg("--edge", 0.030))      # grosor hiperbolico de la arista
SUBDIV = float(arg("--subdiv", 0.22))   # brillo de los espejos internos

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

BG = np.array([10, 13, 32], dtype=np.float64)
EDGE_COL = np.array([0.42, 0.95, 1.00])     # aristas del poligono: cian
SUB_COL = np.array([1.00, 0.78, 0.30])      # subdivision interna: oro
RIM_COL = np.array([0.55, 0.70, 1.00])      # circulo del infinito

THETA_P = np.pi / P
if np.cos(np.pi / Q) / np.sin(THETA_P) <= 1.0:
    sys.exit(f"{{{P},{Q}}} no es hiperbolico: hace falta 1/p + 1/q < 1/2")
AB = np.arccosh(np.cos(np.pi / Q) / np.sin(THETA_P))
XB = np.tanh(AB / 2.0)
MD = (1.0 + XB * XB) / (2.0 * XB)           # centro del espejo circular
MR = np.sqrt(MD * MD - 1.0)                 # radio (ortogonal al disco: MD^2-MR^2=1)


def fold(x, y):
    """Refleja hasta caer en el triangulo fundamental. Devuelve el punto y el
    numero de inversiones (sirve de tinte por 'profundidad' del teselado)."""
    depth = np.zeros(x.shape, dtype=np.float32)
    for _ in range(ITERS):
        # plegado diedral en la cuna [0, pi/p]: cubre los dos espejos rectos
        rad = np.hypot(x, y)
        ang = np.mod(np.arctan2(y, x), 2.0 * THETA_P)
        ang = np.where(ang > THETA_P, 2.0 * THETA_P - ang, ang)
        x, y = rad * np.cos(ang), rad * np.sin(ang)
        # inversion en el espejo circular si el punto quedo del otro lado
        dx, dy = x - MD, y
        s = dx * dx + dy * dy
        inside = s < MR * MR
        if not inside.any():
            break
        k = (MR * MR) / np.where(s > 1e-12, s, 1e-12)
        x = np.where(inside, MD + k * dx, x)
        y = np.where(inside, k * dy, y)
        depth += inside
    return x, y, depth


def mobius_rotation(zx, zy, theta, a):
    """Rotacion hiperbolica de angulo theta alrededor del punto real a.

    Se aplica la INVERSA a las coordenadas del pixel, que es como se consulta
    el teselado ya transformado: T_a . Rot(-theta) . T_-a
    """
    z = zx + 1j * zy
    w = (z - a) / (1.0 - a * z)
    w = w * np.exp(-1j * theta)
    w = (w + a) / (1.0 + a * w)
    return w.real, w.imag


# La grilla no cambia entre frames y el disco ocupa el 44% del cuadro: se
# precomputa una vez y solo se procesan los pixeles de adentro.
_SW, _SH = W * SS, H * SS
_SCALE = (W * FILL) * SS
_yy, _xx = np.mgrid[0:_SH, 0:_SW].astype(np.float64)
_ZX = (_xx - _SW * 0.5) / _SCALE
_ZY = -(_yy - _SH * 0.5) / _SCALE
_R2 = _ZX * _ZX + _ZY * _ZY
_DISK = _R2 < 1.0
_IDX = np.flatnonzero(_DISK.ravel())
_ZXD, _ZYD, _R2D = _ZX.ravel()[_IDX], _ZY.ravel()[_IDX], _R2.ravel()[_IDX]
# anillo del infinito: fijo, se suma tal cual en cada frame
_RIM = np.clip(1.0 - np.abs(np.sqrt(_R2) - 1.0) * _SCALE / 2.2, 0.0, 1.0) ** 2
del _yy, _xx, _ZX, _ZY, _R2
_FLOOR = 1.1 / _SCALE / np.clip(1.0 - _R2D, 1e-4, None)


def render(theta):
    px, py = mobius_rotation(_ZXD, _ZYD, theta, PIVOT)
    fx, fy, depth = fold(px, py)

    # distancias euclideas a los tres espejos, en el marco plegado
    d_circle = np.abs(np.hypot(fx - MD, fy) - MR)
    d_sub = np.minimum(np.abs(fy),
                       np.abs(fx * np.sin(THETA_P) - fy * np.cos(THETA_P)))

    # Grosor constante en metrica hiperbolica: la distancia hiperbolica es
    # ~2*d_euclid/(1-|z|^2), asi que el umbral escala con (1-|z|^2). Se le pone
    # piso en pixeles para que cerca del borde no se pierda por alias.
    met = np.clip(1.0 - (fx * fx + fy * fy), 1e-6, None) * 0.5
    wid = np.maximum(EDGE * met, _FLOOR)

    edge = np.clip(1.0 - d_circle / wid, 0.0, 1.0) ** 1.4
    sub = np.clip(1.0 - d_sub / wid, 0.0, 1.0) ** 1.6 * SUBDIV
    tint = 0.55 + 0.45 * np.cos(depth * 0.9)      # cuerpo tenue por profundidad

    acc = np.zeros((_SH * _SW, 3), dtype=np.float32)
    for c in range(3):
        acc[_IDX, c] = edge * EDGE_COL[c] * tint + sub * SUB_COL[c]
    acc = acc.reshape(_SH, _SW, 3)
    acc += _RIM[:, :, None] * (RIM_COL * 0.55)[None, None, :]

    img = Image.fromarray(np.clip(acc * 255.0, 0, 255).astype(np.uint8), "RGB")
    if SS > 1:
        img = img.resize((W, H), Image.BOX)
    a = np.asarray(img).astype(np.float32) / 255.0
    a = a + 0.45 * gaussian_filter(a, (2.2, 2.2, 0))
    rgb = 1.0 - np.exp(-1.7 * a)
    return np.clip(BG + (255.0 - BG) * rgb, 0, 255).astype(np.uint8)


def main():
    print(f"[hyper] {FRAMES} frames | {W}x{H} (ss{SS}) | {{{P},{Q}}} | "
          f"espejo c={MD:.4f} r={MR:.4f} | pivote {PIVOT}")
    scale_note = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3"]
    events = []
    for f in range(FRAMES):
        theta = 2.0 * np.pi * f / FRAMES        # vuelta exacta -> loop sin costura
        Image.fromarray(render(theta), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))
        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.85})
        if f % 50 == 0 or f == FRAMES - 1:
            print(f"[hyper] {f + 1}/{FRAMES}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[hyper] Eventos: {len(events)} -> {EVENTS_PATH}")
    print(f"[hyper] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
