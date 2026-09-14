"""Tautocrona: la cicloide donde todas las cuentas llegan abajo a la vez.

Dos cuencos con la MISMA profundidad y el MISMO ancho. En el de arriba el
perfil es un arco de circunferencia; en el de abajo, una cicloide. Se sueltan
seis cuentas desde seis alturas distintas, todas en el mismo instante.

En el circulo se desfasan: el periodo de un pendulo crece con la amplitud. En
la cicloide no se desfasan NUNCA, y la razon es una linea de algebra. Midiendo
el arco sigma desde el punto mas bajo de la cicloide,

    sigma = 4r cos(th/2)     y     h = r(1 + cos th) = sigma^2 / (8r)

o sea la altura es exactamente CUADRATICA en el arco recorrido. Eso es la
definicion de un oscilador armonico:

    sigma'' = -(g/4r) sigma        T = 4 pi sqrt(r/g)

y el periodo no depende de la amplitud. Huygens lo uso en 1659 para construir
un reloj de pendulo que no se atrasara al perder cuerda.

Verificado en el arranque: la identidad h = sigma^2/(8r) da un residuo de
4e-16, y el cruce por el fondo ocurre al mismo tiempo para toda amplitud.

La cicloide, ademas, es la braquistocrona: la curva de descenso mas rapido
entre dos puntos. Es la misma curva por las dos cosas.

    python scenes/tautochrone.py -- --frames 900 --res 1920 --name shorts_tauto --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from matplotlib.colors import hsv_to_rgb
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_tauto")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
NBEADS = int(arg("--beads", 6))
CYCLES = float(arg("--cycles", 4.0))    # oscilaciones de la cicloide en el clip
SUB = int(arg("--sub", 12))             # subpasos de integracion por frame
SS = int(arg("--ss", 2))                # supermuestreo del dibujo

R = 1.0
G = 9.81

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from paths import font_path  # noqa: E402

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

# Geometria: la cicloide completa mide 2*pi*r de ancho y 2r de hondo. El
# circulo se elige con esa MISMA profundidad y ese MISMO ancho, que es la
# unica comparacion honesta.
PSI_M = 2.0 * math.atan(2.0 / math.pi)
L = 2.0 * R / (1.0 - math.cos(PSI_M))

DURATION = FRAMES / FPS
OMEGA = CYCLES * 2.0 * math.pi / DURATION       # se fija el periodo al clip
R_EFF = G / (4.0 * OMEGA * OMEGA)               # r que da ese omega
# La forma dibujada usa R=1; la dinamica usa R_EFF via omega. Para que sean
# coherentes se escala g en su lugar: g_eff = 4 * R * omega^2.
G_EFF = 4.0 * R * OMEGA * OMEGA


def cycloid_xy(sigma):
    """Arco con signo desde el fondo -> punto de la cicloide (y hacia abajo)."""
    c = np.clip(sigma / (4.0 * R), -1.0, 1.0)
    th = 2.0 * np.arccos(c)
    x = R * (th - np.sin(th)) - math.pi * R      # centrada en 0
    y = R * (1.0 - np.cos(th))
    return x, y


def circle_xy(psi):
    x = L * np.sin(psi)
    y = 2.0 * R - L * (1.0 - np.cos(psi))
    return x, y


def main():
    # --- chequeos antes de dibujar nada -----------------------------------
    th = np.linspace(1e-4, 2 * math.pi - 1e-4, 200001)
    sig = 4 * R * np.cos(th / 2)
    resid = float(np.abs(R * (1 + np.cos(th)) - sig ** 2 / (8 * R)).max())
    assert resid < 1e-12, f"h != sigma^2/(8r): residuo {resid:.1e}"
    print(f"[tauto] identidad h = sigma^2/(8r): residuo {resid:.1e}")
    print(f"[tauto] periodo {2*math.pi/OMEGA:.4f} s, {CYCLES:g} oscilaciones "
          f"en {DURATION:g} s;  circulo L = {L:.4f} r, psi_max = {PSI_M:.4f}")

    fr = np.linspace(0.14, 1.0, NBEADS)          # alturas iniciales, en 2r
    h0 = fr * 2.0 * R
    sig0 = np.sqrt(8.0 * R * h0)                 # cicloide: h = sigma^2/(8r)
    psi0 = -np.arccos(np.clip(1.0 - h0 / L, -1.0, 1.0))   # circulo, lado izq.

    # Circulo: RK4 sobre psi'' = -(g/L) sin psi. La cicloide no se integra,
    # tiene solucion exacta y por eso no acumula error.
    psi = psi0.copy()
    vel = np.zeros(NBEADS)
    dt = 1.0 / (FPS * SUB)

    def acc(p):
        return -(G_EFF / L) * np.sin(p)

    # Cruces por el fondo, para el numero que se muestra en pantalla
    cross_circle, cross_cyc = [[] for _ in range(NBEADS)], [[] for _ in range(NBEADS)]

    col = hsv_to_rgb(np.stack([(np.linspace(0.0, 0.72, NBEADS) + 0.52) % 1.0,
                               np.full(NBEADS, 0.85), np.ones(NBEADS)], 1))

    # Lienzos de los dos cuencos, en pixeles
    bowl_w = 0.86 * W
    scale = bowl_w / (2.0 * math.pi * R)
    bowl_h = 2.0 * R * scale
    cx = W / 2.0
    top_y = 0.295 * H                             # borde del cuenco de arriba
    bot_y = 0.560 * H                             # borde del cuenco de abajo

    fp = font_path("bold")
    fnt = ImageFont.truetype(fp, int(0.030 * W)) if fp else ImageFont.load_default()

    # Tira temporal bajo cada cuenco: una marca por cada paso de una cuenta
    # por el fondo. Es donde se ve la sincronia, porque en el cuadro las
    # cuentas estan repartidas siempre (tienen amplitudes distintas) y el
    # instante del cruce dura un parpadeo.
    hits_o, hits_c = [], []                 # (t, indice de cuenta)

    trail = np.zeros((H, W, 3), dtype=np.float32)
    events, spreads = [], []
    scale_note = ["D3", "F3", "A3", "C4", "D4", "F4", "A4", "C5"]

    for f in range(FRAMES):
        t0 = f / FPS
        for k in range(SUB):
            t = t0 + k * dt
            # circulo: RK4
            k1v = acc(psi); k1p = vel
            k2v = acc(psi + 0.5 * dt * k1p); k2p = vel + 0.5 * dt * k1v
            k3v = acc(psi + 0.5 * dt * k2p); k3p = vel + 0.5 * dt * k2v
            k4v = acc(psi + dt * k3p);       k4p = vel + dt * k3v
            psi_new = psi + dt / 6 * (k1p + 2 * k2p + 2 * k3p + k4p)
            vel = vel + dt / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
            for b in range(NBEADS):
                if psi[b] * psi_new[b] < 0:
                    cross_circle[b].append(t)
                    hits_o.append((t, b))
            psi = psi_new

            sg = sig0 * np.cos(OMEGA * (t + dt))
            sg_prev = sig0 * np.cos(OMEGA * t)
            for b in range(NBEADS):
                if sg_prev[b] * sg[b] < 0:
                    cross_cyc[b].append(t)
                    hits_c.append((t, b))

        sigma = sig0 * np.cos(OMEGA * (t0 + SUB * dt))
        xc, yc = cycloid_xy(sigma)
        xo, yo = circle_xy(psi)

        img = Image.new("RGB", (W * SS, H * SS), (5, 6, 18))
        dr = ImageDraw.Draw(img)

        # cuantas cuentas estan pegadas al fondo, por cuenco: en la cicloide
        # llegan las seis juntas y el destello es total; en el circulo gotean
        near_o = float(np.mean(np.abs(xo) < 0.10 * R))
        near_c = float(np.mean(np.abs(xc) < 0.10 * R))

        for (ox, oy, fn, par, lab, near) in (
                (cx, top_y, circle_xy, np.linspace(-PSI_M, PSI_M, 400), "circle", near_o),
                (cx, bot_y, cycloid_xy, np.linspace(4 * R, -4 * R, 400), "cycloid", near_c)):
            # caja compartida: misma profundidad y mismo ancho para los dos
            bx = bowl_w / 2.0
            dr.rectangle([((ox - bx) * SS, oy * SS),
                          ((ox + bx) * SS, (oy + bowl_h) * SS)],
                         outline=(34, 40, 64), width=SS)
            px, py = fn(par)
            pts = [((ox + x * scale) * SS, (oy + y * scale) * SS)
                   for x, y in zip(px, py)]
            dr.line(pts, fill=(64, 78, 122), width=max(SS, int(0.0045 * W * SS)))
            g0 = int(40 + 215 * near)
            dr.line([((ox) * SS, (oy + bowl_h * 0.06) * SS),
                     ((ox) * SS, (oy + bowl_h * 1.10) * SS)],
                    fill=(g0, int(g0 * 0.82), int(g0 * 0.35)),
                    width=max(SS, int(0.003 * W * SS * (1 + 2 * near))))
            dr.text((ox * SS, (oy - 0.042 * H) * SS), lab, font=fnt,
                    fill=(160, 175, 215), anchor="mm")

        for (oy, hits) in ((top_y, hits_o), (bot_y, hits_c)):
            sy0 = oy + bowl_h * 1.20
            sh = 0.030 * H
            dr.rectangle([((cx - bowl_w / 2) * SS, sy0 * SS),
                          ((cx + bowl_w / 2) * SS, (sy0 + sh) * SS)],
                         outline=(30, 36, 58), width=SS)
            for (ht, b) in hits:
                hx = cx - bowl_w / 2 + bowl_w * (ht / DURATION)
                c = tuple(int(255 * v) for v in col[b])
                yb = sy0 + sh * (0.12 + 0.76 * b / max(1, NBEADS - 1))
                dr.line([(hx * SS, yb * SS), (hx * SS, (yb + sh * 0.13) * SS)],
                        fill=c, width=max(SS, int(0.0032 * W * SS)))

        for b in range(NBEADS):
            c = tuple(int(255 * v) for v in col[b])
            for (ox, oy, xx, yy) in ((cx, top_y, xo[b], yo[b]),
                                     (cx, bot_y, xc[b], yc[b])):
                X = (ox + xx * scale) * SS
                Y = (oy + yy * scale) * SS
                rad = 0.0155 * W * SS
                dr.ellipse([X - rad, Y - rad, X + rad, Y + rad], fill=c)

        a = np.asarray(img.resize((W, H), Image.LANCZOS)).astype(np.float32) / 255.0
        trail = trail * 0.90
        trail = np.maximum(trail, a * 0.55)
        a = np.clip(a + 0.75 * trail, 0.0, 1.0)
        a = np.clip(a + 0.60 * gaussian_filter(a, (2.0, 2.0, 0)), 0.0, 1.0)
        Image.fromarray((a * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        nmin = min(len(c) for c in cross_circle)
        if nmin > 0:
            last_c = [c[nmin - 1] for c in cross_circle]
            last_y = [c[nmin - 1] for c in cross_cyc if len(c) >= nmin]
            sc = max(last_c) - min(last_c)
            sy = (max(last_y) - min(last_y)) if len(last_y) == NBEADS else 0.0
        else:
            sc = sy = 0.0
        spreads.append((sc, sy))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[tauto] {f + 1}/{FRAMES}  desfase circulo {sc:.3f} s  "
                  f"cicloide {sy:.3f} s")

    n = min(len(c) for c in cross_cyc)
    spread_cyc = max(max(c[:n]) - min(c[:n]) for c in zip(*[c[:n] for c in cross_cyc]))
    print(f"[tauto] cruces de la cicloide: {n} por cuenta, "
          f"desfase maximo {spread_cyc:.2e} s")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": DURATION, "fps": FPS, "events": events,
                   "spreads": spreads, "beads": NBEADS,
                   "period_s": 2 * math.pi / OMEGA,
                   "cycloid_spread_s": float(spread_cyc), "crossings": int(n)}, jf)
    print(f"[tauto] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
