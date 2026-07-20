"""Solitones KdV — SIMULACION NUMERICA EN VIVO (pseudo-espectral), numpy puro.

A diferencia de soliton_field.py (diagrama espacio-tiempo estatico que
scrollea), aqui la ecuacion de Korteweg-de Vries se INTEGRA de verdad
(metodo pseudo-espectral con factor integrante, RK4 estilo Trefethen kdv.m):

    u_t + 6 u u_x + u_xxx = 0        (dominio periodico)

En pantalla:
  - Onda VIVA abajo: el perfil u(x,t) ondulando en tiempo real, con glow.
    Los solitones altos son mas rapidos, alcanzan a los lentos y los
    ATRAVIESAN re-emergiendo con su forma (con el phase-shift real de KdV).
  - Cascada arriba: la historia de u fluyendo hacia arriba (waterfall),
    que teje las trayectorias diagonales y sus cruces.
  - Ripples dispersivos de fondo (radiacion) para textura fina.

Eventos de sonificacion: cuando dos crestas se fusionan (overtake), evento.

Contrato con render/build_clip.py --engine numpy:
    python scenes/soliton_kdv.py -- --frames 900 --res 1920 --name shorts_soliton --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))          # altura
NAME = arg("--name", "shorts_soliton")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
DTF = float(arg("--dtf", 0.05))        # tiempo de simulacion por frame
DT = float(arg("--dt", 5e-4))          # paso interno del integrador

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

if FMT == "9:16":
    H = RES
    W = int(round(RES * 9 / 16))
else:
    W = RES
    H = int(round(RES * 9 / 16))
W -= W % 2
H -= H % 2
RH, RW = H // 2, W // 2  # lienzo interno a mitad de resolucion (rapido)

# ---------------------------------------------------------------- simulacion
N = 512
L = 60.0
x = np.arange(N) * L / N
k = 2.0 * np.pi * np.fft.fftfreq(N, d=L / N)
E = np.exp(1j * k ** 3 * DT / 2.0)
E2 = E * E
g = -3j * DT * k                       # 6 u u_x = 3 (u^2)_x
dealias = np.abs(k) <= (2.0 / 3.0) * np.abs(k).max()

# (kappa, x0): amplitud A=2k^2, velocidad c=4k^2 -> mas alto = mas rapido
KAPPAS = [(1.00, 5.0), (0.80, 22.0), (0.62, 38.0), (0.47, 50.0), (0.36, 12.0)]
UMAX = 2.0 * KAPPAS[0][0] ** 2

u0 = np.zeros(N)
for kap, x0 in KAPPAS:
    d = (x - x0 + L / 2.0) % L - L / 2.0
    u0 += 2.0 * kap ** 2 / np.cosh(kap * d) ** 2
# ripples dispersivos suaves de fondo (textura fina en la cascada)
u0 += 0.035 * np.sin(2 * np.pi * 7 * x / L) + 0.025 * np.sin(2 * np.pi * 11 * x / L + 1.3)

STEPS = int(round(DTF / DT))
ROWS = RH + FRAMES  # prewarm: la cascada arranca llena de historia real


def make_palette():
    stops = [
        (0.00, (4, 8, 24)),
        (0.30, (14, 54, 128)),
        (0.52, (28, 156, 205)),
        (0.72, (118, 226, 222)),
        (0.88, (247, 204, 110)),
        (1.00, (255, 255, 255)),
    ]
    lut = np.zeros((256, 3), dtype=np.float64)
    for i in range(256):
        t = i / 255.0
        for j in range(len(stops) - 1):
            t0, c0 = stops[j]
            t1, c1 = stops[j + 1]
            if t0 <= t <= t1:
                f = (t - t0) / (t1 - t0)
                lut[i] = np.array(c0) * (1 - f) + np.array(c1) * f
                break
    return lut.astype(np.uint8)


PALETTE = make_palette()


def crest_count(u):
    um = np.where(u > 0.30, u, 0.0)
    left = np.roll(um, 1)
    right = np.roll(um, -1)
    return int(((um > left) & (um >= right) & (um > 0.30)).sum())


def simulate():
    """Integra KdV y devuelve S (ROWS, N) + eventos de fusion de crestas."""
    print(f"[kdv] integrando: {ROWS} filas x {STEPS} pasos (dt={DT}, T={ROWS * DTF:.1f})")
    v = np.fft.fft(u0)
    S = np.zeros((ROWS, N), dtype=np.float32)
    events = []
    scale = ["C2", "Eb2", "G2", "C3", "Eb3", "G3"]
    n_prev = None
    for s in range(ROWS):
        for _ in range(STEPS):
            a = g * np.fft.fft(np.real(np.fft.ifft(v)) ** 2)
            b = g * np.fft.fft(np.real(np.fft.ifft(E * (v + a / 2.0))) ** 2)
            c = g * np.fft.fft(np.real(np.fft.ifft(E * v + b / 2.0)) ** 2)
            d4 = g * np.fft.fft(np.real(np.fft.ifft(E2 * v + E * c)) ** 2)
            v = E2 * v + (E2 * a + 2.0 * E * (b + c) + d4) / 6.0
            v *= dealias
        u = np.real(np.fft.ifft(v))
        S[s] = u
        n_now = crest_count(u)
        if n_prev is not None and n_now < n_prev and s >= RH:
            f = s - RH
            h = float(u.max())
            note = "C2" if h > 1.5 else "Eb2" if h > 0.9 else "G2"
            events.append({"frame": f, "note": note,
                           "intensity": round(0.7 + 0.3 * min(h / UMAX, 1.0), 3)})
        n_prev = n_now
        if s % 200 == 0 or s == ROWS - 1:
            print(f"[kdv] fila {s + 1}/{ROWS}  umax={S[s].max():.2f}  crestas={n_now}")

    if len(events) < 6:
        for j in range(8):
            events.append({"frame": int(j * FRAMES / 8), "note": scale[j % len(scale)],
                           "intensity": 0.8})
        events.sort(key=lambda e: e["frame"])
    return S, events


def render(S, events):
    cols = np.linspace(0, N - 1, RW).astype(int)
    y_idx = np.arange(RH)[:, None]
    base = int(0.86 * RH)
    amp = int(0.26 * RH)
    flash_frames = {e["frame"] + i for e in events for i in range(7)}

    # franja inferior: atenuar la cascada para que la onda viva reviente
    strip_top = base - amp - 24
    fade = np.ones((RH, 1), dtype=np.float32)
    ramp = np.linspace(1.0, 0.22, RH - strip_top, dtype=np.float32)
    fade[strip_top:, 0] = ramp

    for f in range(FRAMES):
        # cascada: historia reciente, lo nuevo abajo
        block = S[f:f + RH][:, cols]
        norm = np.clip(block / UMAX, 0.0, 1.0) ** 0.62
        img = PALETTE[np.clip(norm * 255.0, 0, 255).astype(np.uint8)].astype(np.float32)
        img *= fade[:, :, None]

        # onda viva (protagonista): brillante, con nucleo nitido + halo
        u_now = S[f + RH - 1][cols]
        ycurve = base - (np.clip(u_now, 0.0, None) / UMAX * amp).astype(int)
        curve = np.zeros((RH, RW), dtype=np.float32)
        under = (y_idx >= ycurve[None, :]) & (y_idx < base)
        curve[under] = 0.45
        near = np.abs(y_idx - ycurve[None, :]) <= 2
        curve[near] = 1.0
        curve[base:base + 2, :] = 0.30

        cimg = Image.fromarray((np.clip(curve, 0, 1) * 255).astype(np.uint8), "L")
        halo = np.asarray(cimg.filter(ImageFilter.GaussianBlur(3.0)), dtype=np.float32) / 255.0
        core = np.asarray(cimg.filter(ImageFilter.GaussianBlur(0.8)), dtype=np.float32) / 255.0
        glow = np.clip(halo * 0.75 + core * 0.95, 0.0, 1.3)

        warm = f in flash_frames  # colision reciente -> onda mas calida
        add = np.zeros_like(img)
        add[..., 0] = glow * (250 if warm else 195)
        add[..., 1] = glow * (225 if warm else 242)
        add[..., 2] = glow * (170 if warm else 255)

        out = np.clip(img + add, 0, 255).astype(np.uint8)
        Image.fromarray(out, "RGB").resize((W, H), Image.BILINEAR).save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[kdv] frame {f + 1}/{FRAMES}")


def main():
    print(f"[kdv] {FRAMES} frames | {W}x{H} (interno {RW}x{RH}) | N={N} L={L}")
    S, events = simulate()
    render(S, events)
    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[kdv] Eventos: {len(events)} -> {EVENTS_PATH}")
    print(f"[kdv] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
