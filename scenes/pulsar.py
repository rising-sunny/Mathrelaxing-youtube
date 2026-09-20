"""Pulsar: como se saca una senal de abajo del ruido plegando rotaciones.

Una estrella de neutrones gira con su eje magnetico inclinado respecto del de
rotacion. El haz barre el cielo como un faro y, una vez por vuelta, pasa por
encima de nosotros. PSR B1919+21 -- el primero que se encontro, Jocelyn Bell,
1967 -- lo hace cada 1.3373 segundos.

Cada fila de la pila es UNA rotacion. Los pulsos sueltos no son iguales entre
si: cambian de amplitud, de ancho y de fase de una vuelta a la otra. Lo que si
es estable es el PROMEDIO, y ahi esta la matematica: sumando N rotaciones el
ruido crece como sqrt(N) mientras la senal crece como N, asi que

    S/N  ~  sqrt(N)

Medido en la propia escena por ajuste log-log, no citado. Tambien se mide que
plegar con el periodo equivocado destruye todo: un error del 0.1% ya deja el
pulso en nada.

OJO: la senal esta SIMULADA con el modelo estandar (pulso gaussiano con
variabilidad log-normal mas ruido blanco) y el periodo real del pulsar. No son
datos de archivo.

El remate: ochenta rotaciones apiladas de este pulsar son la imagen de la
portada de "Unknown Pleasures" de Joy Division, que viene de la tesis de
Harold Craft (Cornell, 1970) via la Cambridge Encyclopaedia of Astronomy.

    python scenes/pulsar.py -- --frames 900 --res 1920 --name shorts_pulsar --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_pulsar")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
NROWS = int(arg("--rows", 80))          # rotaciones apiladas, como la portada
NPH = int(arg("--nph", 512))            # muestras por rotacion
SNR1 = float(arg("--snr1", 3.5))        # pico del pulso en unidades de ruido
SMOOTH = float(arg("--smooth", 2.5))    # ancho de banda finito del receptor, en bines
SS = int(arg("--ss", 2))
HOLD = int(arg("--hold", 96))
SEED = int(arg("--seed", 11))

P_SEC = 1.3373                          # periodo real de PSR B1919+21
PHI0, PW = 0.44, 0.026
ALPHA = math.radians(38.0)              # inclinacion del eje magnetico

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

BG = (5, 7, 18)


def band_noise(shape, rng):
    """Ruido con ancho de banda finito: blanco suavizado y renormalizado a
    sigma 1. Con ruido blanco puro la pila es una masa solida de estatica;
    un receptor real entrega una linea base ondulada, que es lo que se ve en
    la imagen de la portada."""
    z = rng.normal(0.0, 1.0, shape)
    z = gaussian_filter(z, (0.0, SMOOTH) if len(shape) == 2 else (SMOOTH,),
                        mode="wrap")
    return z / z.std()


def make_rows(n, rng):
    ph = (np.arange(NPH) + 0.5) / NPH
    out = np.empty((n, NPH))
    noise = band_noise((n, NPH), rng)
    for k in range(n):
        amp = SNR1 * math.exp(rng.normal(0.0, 0.55))
        wid = PW * math.exp(rng.normal(0.0, 0.22))
        off = rng.normal(0.0, 0.009)
        d = np.abs(ph - (PHI0 + off))
        d = np.minimum(d, 1 - d)
        out[k] = amp * np.exp(-0.5 * (d / wid) ** 2) + noise[k]
    return out


def peak_rms(profile, w=3.0 * PW):
    """Pico del perfil sobre el ruido de la zona sin pulso.

    Es lo que se muestra en pantalla. El estimador de filtro adaptado de abajo
    es el correcto para MEDIR LA LEY de crecimiento, pero su valor absoluto se
    infla cuando el ruido esta correlacionado (ancho de banda finito), porque
    la ventana tiene menos muestras independientes de las que supone.
    """
    ph = (np.arange(len(profile)) + 0.5) / len(profile)
    d = np.abs(ph - PHI0)
    d = np.minimum(d, 1 - d)
    on, off = d < w, d > 3 * w
    return float((profile[on].max() - profile[off].mean()) / profile[off].std())


def snr(profile, w=3.0 * PW):
    """Filtro adaptado. Usar el MAXIMO de la ventana en su lugar sesga el
    resultado con pocas rotaciones: el maximo del ruido tambien crece con el
    numero de muestras, y el exponente medido baja de 0.5 a 0.29."""
    ph = (np.arange(len(profile)) + 0.5) / len(profile)
    d = np.abs(ph - PHI0)
    d = np.minimum(d, 1 - d)
    on, off = d < w, d > 3 * w
    base, sigma = profile[off].mean(), profile[off].std()
    return float((profile[on] - base).sum() / (sigma * math.sqrt(on.sum())))


# ---------------------------------------------------------------------------
# Geometria 3-D de la magnetosfera.
#
# Marco del mundo: z es el eje de giro. El eje magnetico va inclinado ALPHA
# respecto de z y precesa a su alrededor con la rotacion. La camara mira casi
# a lo largo del eje de giro (INC): es la unica vista en la que el barrido del
# faro se recorre entero dentro del cuadro. El observador esta EN el cono que
# barre el haz, asi que el fogonazo ocurre una vez por vuelta, igual que el
# unico pulso por periodo que tiene el perfil que se pliega abajo.
# ---------------------------------------------------------------------------
INC = math.radians(21.0)
OBS_AZ = math.radians(-118.0)

_U = np.array([0.0, 1.0, 0.0])                        # derecha en pantalla
_V = np.array([-math.cos(INC), 0.0, math.sin(INC)])   # arriba en pantalla
_D = np.array([math.sin(INC), 0.0, math.cos(INC)])    # hacia la camara
OBSV = np.array([math.sin(ALPHA) * math.cos(OBS_AZ),
                 math.sin(ALPHA) * math.sin(OBS_AZ),
                 math.cos(ALPHA)])


def _frame(spin):
    """Terna ortonormal ligada al eje magnetico: (m, e1, e2)."""
    sa, ca = math.sin(ALPHA), math.cos(ALPHA)
    cs, sn = math.cos(spin), math.sin(spin)
    return (np.array([sa * cs, sa * sn, ca]),
            np.array([-sn, cs, 0.0]),
            np.array([-ca * cs, -ca * sn, sa]))


def _project(p):
    """Ortografica. Columnas: x de pantalla, y de pantalla, profundidad."""
    return np.stack([p @ _U, p @ _V, p @ _D], axis=-1)


_TPL = None


def _line_template():
    """Lineas de campo del dipolo, r = L sin^2(theta), en coeficientes sobre
    (m, e1, e2). Se calculan una sola vez: cada cuadro solo las gira."""
    global _TPL
    if _TPL is None:
        out, th = [], np.linspace(0.05, math.pi - 0.05, 80)
        for L in (2.0, 3.1, 4.6, 6.6):
            r = L * np.sin(th) ** 2
            k = r > 0.94                 # el tramo de dentro de la estrella, no
            if k.sum() < 4:
                continue
            rr, tt = r[k], th[k]
            for j in range(10):
                psi = 2 * math.pi * j / 10 + 0.13
                out.append(np.stack([rr * np.cos(tt),
                                     rr * np.sin(tt) * math.cos(psi),
                                     rr * np.sin(tt) * math.sin(psi)], axis=1))
        _TPL = out
    return _TPL


def dipole_lines(spin):
    B = np.stack(_frame(spin))           # filas: m, e1, e2
    return [(q, q[:, 2] / 6.6) for q in
            (_project(abc @ B) for abc in _line_template())]


def beam_rays(spin, reach):
    """Los dos conos de emision como rayos 3-D ya proyectados:
    (extremo cercano, extremo lejano, peso, profundidad del rayo)."""
    m, e1, e2 = _frame(spin)
    out = []
    for sgn in (1.0, -1.0):
        for beta, nray in ((0.0, 1), (math.radians(6.0), 9),
                           (math.radians(12.0), 11), (math.radians(17.0), 13)):
            w = math.exp(-(beta / math.radians(12.0)) ** 2)
            for j in range(nray):
                psi = 2 * math.pi * j / nray + 0.29 * sgn
                d = (math.cos(beta) * sgn * m
                     + math.sin(beta) * (math.cos(psi) * e1 + math.sin(psi) * e2))
                q = _project(np.stack([0.75 * d, reach * d]))
                out.append((q[0], q[1], w, float(d @ _D)))
    return out


def starfield(rng):
    """Fondo fijo: gradiente frio, polvo de baja frecuencia y estrellas."""
    yy, xx = np.mgrid[0:H, 0:W]
    v = (yy / H).astype(np.float32)
    sky = (np.array([0.010, 0.014, 0.034], np.float32)
           + v[..., None] * np.array([0.008, 0.003, -0.014], np.float32))

    dust = gaussian_filter(rng.normal(0.0, 1.0, (H, W)).astype(np.float32),
                           0.055 * W)
    dust = dust / (dust.std() + 1e-9)
    sky += np.maximum(dust, 0.0)[..., None] * np.array([0.015, 0.011, 0.029],
                                                       np.float32)

    n = 1500
    idx = rng.integers(0, H, n) * W + rng.integers(0, W, n)
    b = rng.random(n) ** 3.4             # pocas brillantes, muchas debiles
    t = rng.random(n)                    # de azuladas a ambar
    col = np.stack([0.74 + 0.36 * t, 0.80 + 0.14 * t, 1.0 - 0.24 * t], 1)
    pts = np.stack([np.bincount(idx, weights=b * col[:, c],
                                minlength=H * W).reshape(H, W)
                    for c in range(3)], -1).astype(np.float32)
    sky += pts + 1.6 * gaussian_filter(pts, (0.9, 0.9, 0))

    k = b.argsort()[-24:]                # un punado con halo ancho
    big = np.stack([np.bincount(idx[k], weights=b[k] * col[k, c],
                                minlength=H * W).reshape(H, W)
                    for c in range(3)], -1).astype(np.float32)
    sky += 5.0 * gaussian_filter(big, (2.6, 2.6, 0))
    return sky.astype(np.float32)


def main():
    rng = np.random.default_rng(SEED)

    # --- la ley sqrt(N) ----------------------------------------------------
    # Cada N se mide sobre realizaciones INDEPENDIENTES. Medir todos los N
    # sobre una sola tirada anidada (los primeros n de la misma lista) deja
    # los errores correlacionados y tuerce el ajuste: daba 0.53 de forma
    # reproducible, con tres semillas distintas, y no es fisica sino el
    # metodo de medicion.
    ph_ = (np.arange(NPH) + 0.5) / NPH
    dd = np.minimum(np.abs(ph_ - PHI0), 1 - np.abs(ph_ - PHI0))
    clean = SNR1 * np.exp(-0.5 * (dd / PW) ** 2)
    grng = np.random.default_rng(SEED + 1)
    Ns = np.unique(np.geomspace(8, 2048, 22).astype(int))
    sn = np.array([np.mean([snr(clean + band_noise((n, NPH), grng).mean(axis=0))
                            for _ in range(40)]) for n in Ns])
    a, b = np.polyfit(np.log(Ns), np.log(sn), 1)
    res = np.log(sn) - (a * np.log(Ns) + b)
    r2 = 1 - np.sum(res ** 2) / np.sum((np.log(sn) - np.log(sn).mean()) ** 2)
    assert 0.47 < a < 0.53, f"el exponente medido dio {a:.4f}, no ~0.5"
    print(f"[psr] S/N ~ N^{a:.4f}  (teoria 0.5)   R^2 = {r2:.5f}")

    probe = make_rows(2000, np.random.default_rng(SEED + 2))

    # --- que pasa si el periodo esta mal -----------------------------------
    bad = {}
    for err in (0.001, 0.005):
        sh = (np.arange(400) * err * NPH).astype(int)
        m = np.mean([np.roll(probe[i], sh[i]) for i in range(400)], axis=0)
        bad[err] = peak_rms(m)
    good = peak_rms(probe[:400].mean(axis=0))
    print(f"[psr] plegado de 400 rotaciones (pico/ruido): exacto {good:.1f}; "
          + "; ".join(f"error {e*100:.1f}% -> {v:.1f}" for e, v in bad.items()))

    rows = make_rows(NROWS, rng)

    sky = starfield(rng)
    cx, cy = W / 2.0, 0.352 * H          # centro de la estrella
    Rstar = 0.048 * W
    st_y0, st_y1 = int(0.496 * H), int(0.790 * H)
    mx = int(0.062 * W)
    bw = W - 2 * mx

    # desvanecido lateral de la pila: la ventana se aplica al buffer ya
    # compuesto, no a cada traza, para que el relleno negro tambien se apague
    edge_fade = np.ones(W, np.float32)
    ex = np.arange(W, dtype=np.float32)
    ramp = 0.085 * W
    edge_fade *= np.clip((ex - (mx - 0.25 * ramp)) / ramp, 0.0, 1.0)
    edge_fade *= np.clip(((mx + bw + 0.25 * ramp) - ex) / ramp, 0.0, 1.0)
    edge_fade = 0.5 - 0.5 * np.cos(math.pi * edge_fade)

    yy, xx = np.mgrid[0:H, 0:W]
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    core = (np.exp(-(rr / (Rstar * 0.52)) ** 2)[..., None]
            * np.array([1.0, 0.98, 0.92], np.float32))
    halo = (np.exp(-(rr / (Rstar * 2.3)) ** 2)[..., None]
            * np.array([0.22, 0.46, 0.72], np.float32))
    ox = cx + 6.9 * Rstar * float(OBSV @ _U)
    oy = cy - 6.9 * Rstar * float(OBSV @ _V)
    dob = (np.exp(-(np.sqrt((xx - ox) ** 2 + (yy - oy) ** 2) / (0.012 * W)) ** 2)[..., None]
           * np.array([0.55, 0.75, 1.0], np.float32))
    del yy, xx, rr

    reveal = max(1, FRAMES - HOLD)
    xs = mx + (np.arange(NPH) + 0.5) / NPH * bw

    scale_note = ["D2", "A2", "D3", "F3", "A3", "C4", "D4", "F4"]
    events, shown_n, shown_snr = [], [], []

    for f in range(FRAMES):
        p = min(1.0, (f + 1) / reveal)
        n = max(1, int(round(NROWS * p)))
        prof = rows[:n].mean(axis=0)
        s_pk = peak_rms(prof)
        shown_n.append(n); shown_snr.append(s_pk)
        # la estrella gira en TIEMPO REAL: una vuelta cada P_SEC segundos.
        # La pila de abajo, en cambio, corre acelerada; son dos relojes
        # distintos y el texto solo declara el de la pila.
        spin = 2 * math.pi * (f / FPS) / P_SEC

        # el fogonazo: angulo entre el eje magnetico y el observador. Una vez
        # por vuelta, no dos, porque solo uno de los dos polos lo barre.
        dlt = math.acos(max(-1.0, min(1.0, float(_frame(spin)[0] @ OBSV))))
        lit = math.exp(-(dlt / 0.34) ** 2)

        acc = sky.copy()

        # --- magnetosfera y haces, en 3D ------------------------------------
        star = Image.new("RGB", (W * SS, H * SS), (0, 0, 0))
        dr = ImageDraw.Draw(star)
        # el eje de giro, tenue, para que se lea la inclinacion de la vista
        for sgn in (1.0, -1.0):
            q = _project(np.array([0.0, 0.0, sgn * 3.6]))
            dr.line([(cx * SS, cy * SS),
                     ((cx + q[0] * Rstar) * SS, (cy - q[1] * Rstar) * SS)],
                    fill=(28, 36, 62), width=max(SS, int(0.0012 * W * SS)))

        for pts, depth in dipole_lines(spin):
            X = cx + pts[:, 0] * Rstar
            Y = cy - pts[:, 1] * Rstar
            for i in range(len(X) - 1):
                g = 0.26 + 0.74 * (0.5 + 0.5 * depth[i])   # atras, mas apagado
                col = (int(26 * g), int(92 * g), int(134 * g))
                dr.line([(X[i] * SS, Y[i] * SS), (X[i + 1] * SS, Y[i + 1] * SS)],
                        fill=col, width=max(SS, int(0.0015 * W * SS)))

        # los dos conos de emision, como haces de rayos en 3-D
        for p0, p1, w, dz in beam_rays(spin, 5.6):
            g = w * (0.40 + 0.60 * (0.5 + 0.5 * dz)) * (0.50 + 0.50 * lit)
            col = (int(255 * g), int(178 * g), int(72 * g))
            dr.line([((cx + p0[0] * Rstar) * SS, (cy - p0[1] * Rstar) * SS),
                     ((cx + p1[0] * Rstar) * SS, (cy - p1[1] * Rstar) * SS)],
                    fill=col, width=max(SS, int(0.0032 * W * SS)))

        a_star = np.asarray(star.resize((W, H), Image.LANCZOS)).astype(np.float32) / 255.0
        acc += a_star + 0.85 * gaussian_filter(a_star, (3.0, 3.0, 0))

        # la estrella (nucleo y halo) y el punto del observador
        acc += core + halo * (0.7 + 0.6 * lit) + dob * (0.5 + 1.4 * lit)

        # --- la pila ---------------------------------------------------------
        stk = Image.new("RGB", (W * SS, H * SS), (0, 0, 0))
        ds = ImageDraw.Draw(stk)
        band = st_y1 - st_y0
        step = band / max(1, n)
        amp = 2.0 * step / SNR1
        for i in range(n):
            base = st_y0 + (i + 0.85) * step
            ys = base - amp * np.clip(rows[i], -1.6, None)
            poly = [(float(x) * SS, float(y) * SS) for x, y in zip(xs, ys)]
            poly += [((mx + bw) * SS, base * SS), (mx * SS, base * SS)]
            ds.polygon(poly, fill=(0, 0, 0))
            q = i / max(1, n - 1)          # de violeta arriba a cian abajo
            k = 0.52
            col = (int(255 * k * (0.95 - 0.60 * q)),
                   int(255 * k * (0.30 + 0.62 * q)),
                   int(255 * k))
            ds.line([(float(x) * SS, float(y) * SS) for x, y in zip(xs, ys)],
                    fill=col, width=max(SS, int(0.0020 * W * SS)))

        # el perfil promedio, sin caja, pegado al pie de la pila
        pv = prof - prof.min()
        pv = pv / max(pv.max(), 1e-9)
        ys = st_y1 + 0.052 * H - pv * 0.050 * H
        ds.line([(float(x) * SS, float(y) * SS) for x, y in zip(xs, ys)],
                fill=(255, 190, 96), width=max(SS, int(0.0034 * W * SS)))

        a_stk = np.asarray(stk.resize((W, H), Image.LANCZOS)).astype(np.float32) / 255.0
        a_stk *= edge_fade[None, :, None]     # sin cortes verticales duros
        acc += a_stk + 0.50 * gaussian_filter(a_stk, (2.4, 2.4, 0))

        acc = 1.0 - np.exp(-1.45 * np.maximum(acc, 0.0))
        acc = np.clip(acc + 0.30 * gaussian_filter(acc, (1.3, 1.3, 0)), 0.0, 1.0)
        Image.fromarray((acc * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[psr] {f + 1}/{FRAMES}  rotaciones {n}  pico/ruido {s_pk:.1f}")

    speedup = NROWS * P_SEC / (reveal / FPS)
    print(f"[psr] {NROWS} rotaciones = {NROWS*P_SEC:.0f} s reales en "
          f"{reveal/FPS:.1f} s de clip  ->  x{speedup:.1f}")
    print(f"[psr] la estrella gira en tiempo real: {FRAMES/FPS/P_SEC:.1f} "
          f"vueltas en {FRAMES/FPS:.1f} s")
    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "period_s": P_SEC, "rows": NROWS, "exponent": float(a),
                   "fit_r2": float(r2), "snr_shown": shown_snr, "n_shown": shown_n,
                   "snr_good_400": good, "snr_bad": {str(k): v for k, v in bad.items()},
                   "speedup": speedup}, jf)
    print(f"[psr] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
