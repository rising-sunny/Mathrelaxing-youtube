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

# (n, l, m, elevacion, peso de duracion, corte). m > 0 -> combinacion real.
#
# La elevacion va por estado y no es un capricho: un orbital con m=0 apila
# sus lobulos SOBRE el eje y se lee de perfil, mientras que uno con m=l los
# reparte en un anillo alrededor del eje y solo se lee desde arriba. Con una
# camara unica la mitad de la lista sale como la misma mancuerna borrosa.
#
# Las duraciones tampoco son iguales. El 1s es una esfera y no hay giro que
# la mueva: dejarle 1.9 s al principio es regalar los segundos que deciden
# si alguien se queda. Se le da menos de un segundo y el sobrante va a los
# dos ultimos, que son los que valen la pena mirar.
STATES = [
    (1, 0, 0, 26.0, 0.55, False),  # 1s   una esfera
    (2, 1, 0, 13.0, 0.80, False),  # 2p   la mancuerna, de perfil
    (3, 2, 0, 20.0, 1.00, False),  # 3d   mancuerna con anillo en la cintura
    (4, 3, 0, 11.0, 1.00, False),  # 4f   cuatro lobulos apilados en el eje
    (5, 0, 0, 30.0, 1.25, True),   # 5s   cuatro capas anidadas, partido
    (5, 3, 2, 48.0, 1.10, False),  # 5f   con un nodo radial
    (6, 4, 4, 66.0, 1.30, False),  # 6g   ocho lobulos, casi desde arriba
    (7, 6, 6, 72.0, 2.00, False),  # 7i   doce lobulos, desde arriba
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


def volume(n, l, m, nv, half, cut=False):
    """Muestrea psi real en un cubo de lado 2*half.

    Con cut=True se quita media esfera. Hace falta para los estados con
    nodos radiales: al integrar de frente a fondo, las capas concentricas se
    tapan unas a otras y los signos opuestos se suman a gris, asi que el 5s
    sale como una bola turbia. Partido, se ven las capas como en una geoda.
    """
    ax = np.linspace(-half, half, nv, dtype=np.float32)
    Z, Y, X = np.meshgrid(ax, ax, ax, indexing="ij")
    r = np.sqrt(X * X + Y * Y + Z * Z)
    np.maximum(r, 1e-9, out=r)
    theta = np.arccos(np.clip(Z / r, -1.0, 1.0))
    phi = np.arctan2(Y, X)
    v = radial(n, l, r) * angular(l, m, theta, phi)
    if cut:
        v = np.where(Y > 0, 0.0, v)
    return v.astype(np.float32)


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
# luz en coordenadas del arreglo (z, y, x): arriba, hacia la camara
# y un poco a la izquierda
LIGHT = np.array([0.58, -0.61, -0.54], np.float32)


def project(vol, spin, tilt, gain):
    """Emision-absorcion de frente a fondo CON sombreado por gradiente.

    Sin el sombreado el resultado es una mancha de aerografo: la integral de
    una densidad no tiene superficie y los lobulos salen planos. El gradiente
    de |psi| da la normal de la isosuperficie, y con eso los lobulos se ven
    solidos y con volumen.

    El compositing va por rebanadas y no sobre un arreglo (nv,nv,nv,3): a
    256^3 ese arreglo de color solo ya son 200 MB.
    """
    nv = vol.shape[0]
    c = (nv - 1) / 2.0
    ct, st = math.cos(tilt), math.sin(tilt)
    cs, ss = math.cos(spin), math.sin(spin)
    # indices del arreglo: (z, y, x). Primero gira sobre z (plato), luego
    # inclina sobre x. y es la profundidad hacia la camara.
    rz = np.array([[1, 0, 0], [0, cs, -ss], [0, ss, cs]], np.float64)
    rx = np.array([[ct, -st, 0], [st, ct, 0], [0, 0, 1]], np.float64)
    M = rz @ rx
    off = np.array([c, c, c]) - M @ np.array([c, c, c])
    v = affine_transform(vol, M, offset=off, order=1, prefilter=False)

    # Curvas duras a proposito. Con exponentes suaves el orbital sale como
    # una nube de algodon: |psi| es no nulo casi en todas partes y una rampa
    # casi lineal enciende tambien la cola, que es justo lo que no interesa.
    a = np.clip(np.abs(v) * gain, 0.0, 1.0)
    gz, gy, gx = np.gradient(a)
    gn = np.sqrt(gz * gz + gy * gy + gx * gx)
    np.maximum(gn, 1e-7, out=gn)

    out = np.zeros((nv, nv, 3), np.float32)
    trans = np.ones((nv, nv), np.float32)
    for j in range(nv):
        aj = a[:, j, :]
        # la normal de la isosuperficie apunta hacia donde |psi| baja
        lam = -(LIGHT[0] * gz[:, j, :] + LIGHT[1] * gy[:, j, :]
                + LIGHT[2] * gx[:, j, :]) / gn[:, j, :]
        shade = 0.42 + 0.72 * np.clip(lam, 0.0, 1.0)
        d = (aj ** 2.6) * 0.44                       # opacidad por voxel
        e = (aj ** 2.2) * shade
        col = np.where((v[:, j, :] > 0)[..., None], WARM, COOL) * e[..., None]
        out += trans[..., None] * d[..., None] * col
        trans *= 1.0 - d
    return out


def main():
    worst_norm, worst_e, ovl = verify()

    w = np.array([st[4] for st in STATES], float)
    lens = np.maximum(2, np.round(w / w.sum() * FRAMES).astype(int))
    lens[-1] += FRAMES - lens.sum()          # el ultimo absorbe el redondeo
    starts = np.concatenate([[0], np.cumsum(lens)])
    boxes, nodes = [], []
    for (n, l, m, _t, _w, _c) in STATES:
        boxes.append(box_radius(n, l))
        nodes.append((n - l - 1, l))
    print("[h] " + " | ".join(
        f"{n}{'spdfghi'[l]}{'' if m == 0 else m} caja {b:.0f} a0"
        for (n, l, m, _t, _w, _c), b in zip(STATES, boxes)))

    # El brillo se normaliza por estado: |psi| cae varios ordenes de magnitud
    # al subir n. Se usa un PERCENTIL, no el maximo: en las orbitales s el
    # pico central es enorme comparado con las capas de fuera, y dividir por
    # el maximo deja el 5s como un punto con cuatro capas invisibles.
    def build(i):
        n, l, m, _t, _w, cut = STATES[i]
        v = volume(n, l, m, NV, boxes[i], cut)
        a = np.abs(v)
        ref = np.percentile(a[a > 0], 99.86)
        return v, 1.0 / (ref + 1e-30)

    def pose(i, k, seg):
        """Giro y elevacion del estado i en el cuadro k de su tramo.

        Un estado partido solo enseña las capas cuando el corte mira a la
        camara, asi que en vez de dar vueltas se mece alrededor de esa
        posicion. Los demas giran como un plato."""
        st = STATES[i]
        if st[5]:
            sp = math.pi + 0.55 * math.sin(2 * math.pi * k / seg)
        else:
            sp = 2 * math.pi * SPINS * (k / seg)
        return sp, math.radians(st[3]) + math.radians(7.0) * math.sin(
            2 * math.pi * k / seg)

    cur, gain = build(0)
    nxt = None
    scale_note = ["D2", "A2", "D3", "F3", "A3", "C4", "E4", "A4"]
    events, shown = [], []

    for f in range(FRAMES):
        i = int(np.searchsorted(starts, f, side="right") - 1)
        i = min(i, len(STATES) - 1)
        seg = int(lens[i])
        k = f - int(starts[i])                            # cuadro dentro del tramo
        spin, tilt = pose(i, k, seg)

        fade = min(FADE, max(1, seg // 3))
        if nxt is None and i + 1 < len(STATES) and k >= seg - fade:
            nxt, gain_n = build(i + 1)

        img = project(cur, spin, tilt, gain)
        if nxt is not None:
            t = (k - (seg - fade)) / fade
            t = t * t * (3 - 2 * t)
            nsp, ntl = pose(i + 1, 0, int(lens[i + 1]))
            img = (1 - t) * img + t * project(nxt, nsp, ntl, gain_n)
            if k == seg - 1:
                cur, gain, nxt = nxt, gain_n, None

        sg = NV / 150.0
        a = 1.0 - np.exp(-5.2 * np.maximum(img, 0.0))
        # mascara de enfoque: la integracion volumetrica ya difumina de por
        # si, y encima viene una ampliacion de 256 a mas de 1000 pixeles
        a = np.clip(a + 0.55 * (a - gaussian_filter(a, (1.3, 1.3, 0))), 0.0, 1.0)
        a = np.clip(a + 0.17 * gaussian_filter(a, (sg, sg, 0)), 0.0, 1.0)

        side = int(W_PIX * 1.02)
        tile = np.asarray(
            Image.fromarray((a * 255).astype(np.uint8), "RGB").resize(
                (side, side), Image.LANCZOS)).astype(np.float32) / 255.0
        # aditivo, no pegado: el render llega a cero en los bordes y pegarlo
        # deja un cuadrado negro recortado sobre el fondo del cuadro
        out = np.tile(np.array([4, 6, 15], np.float32) / 255.0, (H_PIX, W_PIX, 1))
        x0 = (W_PIX - side) // 2
        y0 = int(0.455 * H_PIX) - side // 2
        xs, ys = slice(max(0, x0), min(W_PIX, x0 + side)), \
            slice(max(0, y0), min(H_PIX, y0 + side))
        out[ys, xs] += tile[ys.start - y0:ys.stop - y0, xs.start - x0:xs.stop - x0]
        Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        n, l, m, _t, _w, _c = STATES[i]
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
