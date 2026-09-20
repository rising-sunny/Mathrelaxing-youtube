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

    # bandas del cuadro
    ins_y0, ins_y1 = int(0.262 * H), int(0.338 * H)
    st_y0, st_y1 = int(0.352 * H), int(0.706 * H)
    av_y0, av_y1 = int(0.716 * H), int(0.778 * H)
    mx = int(0.065 * W)
    bw = W - 2 * mx

    reveal = max(1, FRAMES - HOLD)
    xs = mx + (np.arange(NPH) + 0.5) / NPH * bw

    scale_note = ["D2", "A2", "D3", "F3", "A3", "C4", "D4", "F4"]
    events, shown_n, shown_snr = [], [], []

    for f in range(FRAMES):
        p = min(1.0, (f + 1) / reveal)
        n = max(1, int(round(NROWS * p)))
        prof = rows[:n].mean(axis=0)
        s = peak_rms(prof)
        shown_n.append(n); shown_snr.append(s)

        img = Image.new("RGB", (W * SS, H * SS), BG)
        dr = ImageDraw.Draw(img)

        # --- faro: la estrella y el haz que barre --------------------------
        cx, cy = W / 2.0, (ins_y0 + ins_y1) / 2.0
        rr = (ins_y1 - ins_y0) * 0.30
        theta = 2 * math.pi * (n - 1 + (p * reveal * NROWS / max(1, reveal)) % 1)
        theta = 2 * math.pi * ((f / reveal) * NROWS)
        obs = math.radians(-18.0)                      # direccion del observador
        for sgn in (1, -1):
            ang = theta if sgn > 0 else theta + math.pi
            half = math.radians(13.0)
            L = (ins_y1 - ins_y0) * 1.9
            pts = [(cx * SS, cy * SS)]
            for t in (ang - half, ang, ang + half):
                pts.append(((cx + L * math.cos(t) * math.cos(ALPHA)) * SS,
                            (cy - L * math.sin(t)) * SS))
            dr.polygon(pts, fill=(28, 70, 104))
        dr.ellipse([(cx - rr) * SS, (cy - rr) * SS, (cx + rr) * SS, (cy + rr) * SS],
                   fill=(236, 242, 255))
        ox = cx + (ins_y1 - ins_y0) * 1.55 * math.cos(obs) * math.cos(ALPHA)
        oy = cy - (ins_y1 - ins_y0) * 1.55 * math.sin(obs)
        d_ang = abs((theta - obs + math.pi) % (2 * math.pi) - math.pi)
        d_ang = min(d_ang, abs((theta + math.pi - obs + math.pi) % (2 * math.pi) - math.pi))
        lit = math.exp(-(d_ang / 0.30) ** 2)
        orr = 0.010 * W * (1 + 0.8 * lit)
        dr.ellipse([(ox - orr) * SS, (oy - orr) * SS, (ox + orr) * SS, (oy + orr) * SS],
                   fill=(int(90 + 165 * lit), int(120 + 120 * lit), int(150 + 90 * lit)))

        # --- la pila: siempre TODAS las filas, repartidas en la banda ------
        band = st_y1 - st_y0
        step = band / max(1, n)
        # El dibujo se escala al ESPACIADO DE FILA: el pico tipico ocupa dos
        # filas y el ruido un decimo de fila. Escalando en unidades absolutas,
        # con pocas filas las curvas se salen del cuadro y con muchas la pila
        # se vuelve una mancha.
        amp = 2.0 * step / SNR1
        for i in range(n):
            base = st_y0 + (i + 0.85) * step
            ys = base - amp * np.clip(rows[i], -1.6, None)
            poly = [(float(x) * SS, float(y) * SS) for x, y in zip(xs, ys)]
            poly += [((mx + bw) * SS, base * SS), (mx * SS, base * SS)]
            dr.polygon(poly, fill=BG)
            g = 190 + int(55 * i / max(1, n - 1))
            dr.line([(float(x) * SS, float(y) * SS) for x, y in zip(xs, ys)],
                    fill=(g, g, min(255, g + 12)), width=max(SS, int(0.0022 * W * SS)))

        # --- perfil promedio ------------------------------------------------
        dr.rectangle([mx * SS, av_y0 * SS, (mx + bw) * SS, av_y1 * SS],
                     outline=(40, 48, 74), width=SS)
        pv = prof - prof.min()
        pv = pv / max(pv.max(), 1e-9)
        ys = av_y1 - 4 - pv * (av_y1 - av_y0 - 10)
        dr.line([(float(x) * SS, float(y) * SS) for x, y in zip(xs, ys)],
                fill=(255, 186, 92), width=max(SS, int(0.0030 * W * SS)))

        a_img = np.asarray(img.resize((W, H), Image.LANCZOS)).astype(np.float32) / 255.0
        a_img = np.clip(a_img + 0.40 * gaussian_filter(a_img, (1.4, 1.4, 0)), 0.0, 1.0)
        Image.fromarray((a_img * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[psr] {f + 1}/{FRAMES}  rotaciones {n}  S/N {s:.1f}")

    speedup = NROWS * P_SEC / (reveal / FPS)
    print(f"[psr] {NROWS} rotaciones = {NROWS*P_SEC:.0f} s reales en "
          f"{reveal/FPS:.1f} s de clip  ->  x{speedup:.1f}")
    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "period_s": P_SEC, "rows": NROWS, "exponent": float(a),
                   "fit_r2": float(r2), "snr_shown": shown_snr, "n_shown": shown_n,
                   "snr_good_400": good, "snr_bad": {str(k): v for k, v in bad.items()},
                   "speedup": speedup}, jf)
    print(f"[psr] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
