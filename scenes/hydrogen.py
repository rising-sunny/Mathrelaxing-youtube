"""
Orbitales del atomo de hidrogeno, renderizados en volumen.

    psi_nlm(r,t,f) = R_nl(r) Y_lm(t,f)

    R_nl(r) = sqrt( (2/n)^3 (n-l-1)! / (2n (n+l)!) )
              e^(-rho/2) rho^l L_(n-l-1)^(2l+1)(rho),    rho = 2r/n

Es el unico atomo que se resuelve exactamente, y de esa solucion salen tres
cosas que aqui se COMPRUEBAN, no se citan:

  * la norma vale 1,
  * la parte radial tiene exactamente n-l-1 nodos,
  * al aplicarle el hamiltoniano radial por diferencias finitas sale el
    autovalor -1/(2n^2), que es la formula de Rydberg.

Se dibujan combinaciones REALES (las de los libros de quimica: p_x, d_xy,
...), que tambien son autoestados porque los m degenerados se pueden mezclar.
El color es el SIGNO de psi, no su modulo: la fase es fisica y es lo que
hace que dos orbitales se sumen o se cancelen al formar un enlace.

Uso:
    python scenes/hydrogen.py -- --frames 900 --res 1920 --name shorts_h
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import affine_transform, gaussian_filter
from scipy.special import factorial, genlaguerre, sph_harm_y

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_h")
FPS = int(arg("--fps", 60))
NV = int(arg("--nv", 256))              # lado del cubo de voxeles
FADE = int(arg("--fade", 14))           # cuadros de cruce entre orbitales
TILT = math.radians(float(arg("--tilt", 42.0)))
SPINS = float(arg("--spins", 1.30))     # vueltas de plato por orbital

# (n, l, m, elevacion). m > 0 -> combinacion real, la de los libros.
#
# La elevacion va por estado y no es un capricho: un orbital con m=0 apila
# sus lobulos SOBRE el eje y se lee de perfil, mientras que uno con m=l los
# reparte en un anillo alrededor del eje y solo se lee desde arriba. Con una
# camara unica la mitad de la lista sale como la misma mancuerna borrosa.
STATES = [
    (1, 0, 0, 26.0),    # 1s   una esfera
    (2, 1, 0, 13.0),    # 2p   la mancuerna, de perfil
    (3, 2, 0, 20.0),    # 3d   mancuerna con anillo en la cintura
    (4, 3, 0, 11.0),    # 4f   cuatro lobulos apilados en el eje
    (5, 0, 0, 30.0),    # 5s   cuatro capas anidadas
    (5, 3, 2, 48.0),    # 5f   con un nodo radial
    (6, 4, 4, 66.0),    # 6g   ocho lobulos, casi desde arriba
    (7, 6, 6, 72.0),    # 7i   doce lobulos, desde arriba
]

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

W_PIX, H_PIX = int(round(RES * 9 / 16)), RES
W_PIX -= W_PIX % 2
H_PIX -= H_PIX % 2


# --------------------------------------------------------------------------
# La funcion de onda
# --------------------------------------------------------------------------
def radial(n, l, r):
    """R_nl en unidades atomicas (a0 = 1)."""
    rho = 2.0 * r / n
    norm = math.sqrt((2.0 / n) ** 3 * factorial(n - l - 1)
                     / (2.0 * n * factorial(n + l)))
    return norm * np.exp(-rho / 2) * rho ** l * genlaguerre(n - l - 1, 2 * l + 1)(rho)


def angular(l, m, theta, phi):
    """Armonico esferico REAL. Para m > 0 es la combinacion (Y_l^-m + (-1)^m
    Y_l^m)/sqrt(2), que es la que da los lobulos de los libros de quimica y
    sigue siendo autoestado por la degeneracion en m."""
    if m == 0:
        return sph_harm_y(l, 0, theta, phi).real
    return math.sqrt(2.0) * (-1) ** m * sph_harm_y(l, m, theta, phi).real


def box_radius(n, l, rel=0.07):
    """Radio hasta donde el orbital SE VE, no hasta donde existe.

    Con una fraccion acumulada de probabilidad la caja sale demasiado grande:
    la cola pesa en la integral pero la curva de transferencia la apaga, y el
    orbital queda como un punto en medio del cuadro. Se toma el ultimo radio
    donde la densidad radial pasa del 7% de su maximo."""
    r = np.linspace(1e-6, 60.0 * n * n, 40000)
    p = (radial(n, l, r) * r) ** 2
    k = np.nonzero(p > rel * p.max())[0]
    return float(r[k[-1]]) * 1.06


def volume(n, l, m, nv, half):
    """Muestrea psi real en un cubo de lado 2*half."""
    ax = np.linspace(-half, half, nv, dtype=np.float32)
    Z, Y, X = np.meshgrid(ax, ax, ax, indexing="ij")
    r = np.sqrt(X * X + Y * Y + Z * Z)
    np.maximum(r, 1e-9, out=r)
    theta = np.arccos(np.clip(Z / r, -1.0, 1.0))
    phi = np.arctan2(Y, X)
    return (radial(n, l, r) * angular(l, m, theta, phi)).astype(np.float32)


# --------------------------------------------------------------------------
# Verificacion
# --------------------------------------------------------------------------
def verify():
    """Norma, numero de nodos y autovalor de energia, para los 28 estados
    con n <= 7. El del hamiltoniano es el fuerte: se aplica el operador por
    diferencias finitas y tiene que salir la formula de Rydberg."""
    nr, rmax = 600000, 260.0
    r = np.linspace(rmax / nr, rmax, nr)
    h = r[1] - r[0]
    worst_norm = worst_e = 0.0
    bad_nodes = []
    for n in range(1, 8):
        for l in range(0, n):
            u = radial(n, l, r) * r          # u = rR obedece -u''/2 + Veff u = E u
            worst_norm = max(worst_norm, abs(np.trapezoid(u * u, r) - 1.0))
            d2 = np.empty_like(u)
            d2[1:-1] = (u[2:] - 2 * u[1:-1] + u[:-2]) / h ** 2
            d2[0], d2[-1] = d2[1], d2[-2]
            hu = -0.5 * d2 + (-1.0 / r + l * (l + 1) / (2 * r * r)) * u
            # se descarta el origen: ahi u va como r^(l+1) y la diferencia
            # finita de segundo orden no lo resuelve
            k = r > 0.35
            e = np.trapezoid(u[k] * hu[k], r[k]) / np.trapezoid(u[k] * u[k], r[k])
            worst_e = max(worst_e, abs(e / (-0.5 / n ** 2) - 1.0))
            rr = radial(n, l, r)[(r > 1e-3) & (r < 60 * n)]
            if int(np.sum(np.diff(np.sign(rr)) != 0)) != n - l - 1:
                bad_nodes.append((n, l))
    ovl = 0.0
    for l in range(0, 4):
        for n1 in range(l + 1, 8):
            for n2 in range(n1 + 1, 8):
                ovl = max(ovl, abs(np.trapezoid(
                    radial(n1, l, r) * radial(n2, l, r) * r * r, r)))
    print(f"[h] 28 estados con n<=7: norma a {worst_norm:.1e}, energia "
          f"-1/(2n^2) a {worst_e:.1e} relativo, ortogonalidad a {ovl:.1e}")
    assert worst_norm < 1e-7, f"la norma se va en {worst_norm:.2e}"
    assert worst_e < 1e-5, f"la energia no da Rydberg: error {worst_e:.2e}"
    assert ovl < 1e-7, f"los estados no son ortogonales: {ovl:.2e}"
    assert not bad_nodes, f"cuentan mal los nodos: {bad_nodes}"
    return worst_norm, worst_e, ovl


# --------------------------------------------------------------------------
# Render volumetrico
# --------------------------------------------------------------------------
WARM = np.array([1.00, 0.62, 0.16], np.float32)    # psi > 0
COOL = np.array([0.18, 0.66, 1.00], np.float32)    # psi < 0


def project(vol, spin, tilt, gain):
    """Emision-absorcion de frente a fondo. El eje de giro del plato es el
    vertical de la pantalla; la elevacion inclina el eje del orbital para
    que las estructuras anulares se lean."""
    nv = vol.shape[0]
    c = (nv - 1) / 2.0
    ct, st = math.cos(tilt), math.sin(tilt)
    cs, ss = math.cos(spin), math.sin(spin)
    # indices del arreglo: (z, y, x). Primero gira sobre z (plato), luego
    # inclina sobre x.
    rz = np.array([[1, 0, 0], [0, cs, -ss], [0, ss, cs]], np.float64)
    rx = np.array([[ct, -st, 0], [st, ct, 0], [0, 0, 1]], np.float64)
    M = rz @ rx
    off = np.array([c, c, c]) - M @ np.array([c, c, c])
    v = affine_transform(vol, M, offset=off, order=1, prefilter=False)

    # Curvas duras a proposito. Con exponentes suaves el orbital sale como
    # una nube de algodon: |psi| es no nulo casi en todas partes y una rampa
    # casi lineal enciende tambien la cola, que es justo lo que no interesa.
    a = np.clip(np.abs(v) * gain, 0.0, 1.0)
    dens = (a ** 2.6) * 0.44                             # opacidad por voxel
    emis = a ** 2.4
    col = np.where((v > 0)[..., None], WARM, COOL) * emis[..., None]

    # de frente a fondo a lo largo del eje y del arreglo (la profundidad)
    out = np.zeros((nv, nv, 3), np.float32)
    trans = np.ones((nv, nv), np.float32)
    for j in range(nv):
        d = dens[:, j, :]
        out += trans[..., None] * d[..., None] * col[:, j, :, :]
        trans *= 1.0 - d
    return out


def main():
    worst_norm, worst_e, ovl = verify()

    seg = FRAMES // len(STATES)
    boxes, nodes = [], []
    for (n, l, m, _t) in STATES:
        boxes.append(box_radius(n, l))
        nodes.append((n - l - 1, l))
    print("[h] " + " | ".join(
        f"{n}{'spdfghi'[l]}{'' if m == 0 else m} caja {b:.0f} a0"
        for (n, l, m, _t), b in zip(STATES, boxes)))

    # El brillo se normaliza por estado: |psi| cae varios ordenes de magnitud
    # al subir n. Se usa un PERCENTIL, no el maximo: en las orbitales s el
    # pico central es enorme comparado con las capas de fuera, y dividir por
    # el maximo deja el 5s como un punto con cuatro capas invisibles.
    def build(i):
        n, l, m, _t = STATES[i]
        v = volume(n, l, m, NV, boxes[i])
        a = np.abs(v)
        ref = np.percentile(a[a > 0], 99.86)
        return v, 1.0 / (ref + 1e-30)

    cur, gain = build(0)
    nxt = None
    scale_note = ["D2", "A2", "D3", "F3", "A3", "C4", "E4", "A4"]
    events, shown = [], []

    for f in range(FRAMES):
        i = min(len(STATES) - 1, f // seg)
        k = f - i * seg                                   # cuadro dentro del tramo
        spin = 2 * math.pi * SPINS * (k / seg)
        base = math.radians(STATES[i][3])
        tilt = base + math.radians(7.0) * math.sin(2 * math.pi * k / seg)

        fade = min(FADE, max(1, seg // 3))
        if nxt is None and i + 1 < len(STATES) and k >= seg - fade:
            nxt, gain_n = build(i + 1)

        img = project(cur, spin, tilt, gain)
        if nxt is not None:
            t = (k - (seg - fade)) / fade
            t = t * t * (3 - 2 * t)
            nb = math.radians(STATES[i + 1][3])
            img = (1 - t) * img + t * project(
                nxt, spin - 2 * math.pi * SPINS,
                nb + math.radians(7.0) * math.sin(2 * math.pi * k / seg), gain_n)
            if k == seg - 1:
                cur, gain, nxt = nxt, gain_n, None

        sg = NV / 150.0
        a = 1.0 - np.exp(-3.2 * np.maximum(img, 0.0))
        a = np.clip(a + 0.26 * gaussian_filter(a, (sg, sg, 0)), 0.0, 1.0)

        side = int(W_PIX * 1.02)
        tile = Image.fromarray((a * 255).astype(np.uint8), "RGB").resize(
            (side, side), Image.LANCZOS)
        frame = Image.new("RGB", (W_PIX, H_PIX), (4, 6, 15))
        frame.paste(tile, ((W_PIX - side) // 2, int(0.455 * H_PIX) - side // 2))
        frame.save(os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        n, l, m, _t = STATES[i]
        shown.append({"n": n, "l": l, "m": m, "box": boxes[i],
                      "radial_nodes": nodes[i][0], "angular_nodes": nodes[i][1],
                      "energy_ev": -13.605693122994 / (n * n)})
        if k == 0:
            events.append({"frame": f, "note": scale_note[i % 8], "intensity": 0.85})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[h] {f+1}/{FRAMES}  {n}{'spdfghi'[l]}"
                  f"{'' if m == 0 else m}  caja {boxes[i]:.0f} a0")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "states": [list(s) for s in STATES], "boxes": boxes,
                   "nv": NV, "shown": shown, "worst_norm": worst_norm,
                   "worst_energy_rel": worst_e, "orthogonality": ovl},
                  jf)
    print(f"[h] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
