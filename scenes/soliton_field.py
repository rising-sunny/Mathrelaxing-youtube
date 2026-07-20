"""Solitones KdV — diagrama espacio-tiempo, loop continuo, numpy puro.

Eje horizontal = espacio (periodico, ancho W). Eje vertical = tiempo. Cada
soliton es un pulso sech^2 que viaja a velocidad proporcional a su amplitud
(relacion de la ecuacion de Korteweg-de Vries: mas alto = mas rapido = mas
angosto). En el diagrama aparecen como franjas luminosas diagonales; cuando dos
se cruzan, se atraviesan y re-emergen con la misma forma — la propiedad que
define a un soliton.

Loop exacto por construccion: el campo se precomputa periodico en el espacio
(periodo W) y en el tiempo (periodo R filas), y cada soliton avanza un numero
ENTERO de vueltas sobre R filas. El scroll recorre exactamente R filas en N
frames, asi que el frame N == frame 0.

Contrato con render/build_clip.py --engine numpy:
    python scenes/soliton_field.py -- --frames 900 --res 1920 --name shorts_soliton --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json

Por que ondas/solitones: es la familia con MEJOR promedio del canal (802 vistas)
y no tenia ninguna escena.
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
SEED_PHASE = float(arg("--phase", 0.0))  # corre las posiciones iniciales

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

R = 2000  # filas del campo maestro (periodo temporal)

# Solitones: (amplitud, m = vueltas enteras sobre R filas, x0 relativo).
# La relacion KdV liga amplitud, velocidad y ancho: mas alto => mas rapido
# (m mayor) => mas angosto (w ~ 1/sqrt(A)).
SOLITONS = [
    (1.00, 6, 0.50),   # alto, rapido, angosto  -> franja empinada y brillante
    (0.55, 3, 0.10),   # medio
    (0.30, 1, 0.80),   # bajo, lento, ancho     -> franja casi horizontal
]
WIDTH_K = 30.0  # ancho del soliton mas alto, en px


def make_palette():
    """Paleta oceanica luminosa: azul profundo -> cian -> ambar -> blanco."""
    stops = [
        (0.00, (5, 9, 28)),
        (0.30, (16, 58, 132)),
        (0.52, (30, 160, 205)),
        (0.72, (120, 226, 220)),
        (0.88, (245, 205, 120)),
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


def build_master():
    """Campo espacio-tiempo (R, W), periodico en ambos ejes."""
    xs = np.arange(W)
    rows = np.arange(R)
    u = np.zeros((R, W), dtype=np.float64)
    centers = []  # (A, center_por_fila) para eventos
    for A_i, m_i, x0_rel in SOLITONS:
        v_i = m_i * W / R  # px de espacio por fila -> m_i vueltas enteras en R
        w_i = WIDTH_K / np.sqrt(A_i)
        x0 = (x0_rel + SEED_PHASE) * W
        center = (x0 + v_i * rows) % W                # (R,)
        d = xs[None, :] - center[:, None]             # (R, W)
        d = (d + W / 2.0) % W - W / 2.0               # distancia periodica
        z = np.clip(np.abs(d) / w_i, 0.0, 30.0)
        u += A_i / np.cosh(z) ** 2
        centers.append((A_i, center))
    norm = u / u.max()
    norm = np.power(norm, 0.78)                       # realza crestas
    idx8 = np.clip(norm * 255.0, 0, 255).astype(np.uint8)
    rgb = PALETTE[idx8]
    # Glow suave, una sola vez sobre el maestro (barato y consistente)
    rgb = np.asarray(Image.fromarray(rgb, "RGB").filter(ImageFilter.GaussianBlur(1.3)))
    return rgb, centers


def main():
    print(f"[soliton] {FRAMES} frames | {W}x{H} | maestro R={R}")
    master, centers = build_master()

    # Eventos de sonificacion: una "colision" cuando el soliton mas alto pasa por
    # el centro del espacio (x = W/2) en la fila que se ve al centro del frame.
    scale = ["C2", "Eb2", "G2", "C3", "Eb3", "G3"]
    events = []
    A_top, center_top = centers[0]
    prev_side = None
    for f in range(FRAMES):
        off = int(round(f * R / FRAMES)) % R
        mid_row = (off + H // 2) % R
        cx = center_top[mid_row]
        side = cx > (W / 2.0)
        if prev_side is not None and side != prev_side:
            events.append({
                "frame": f,
                "note": scale[len(events) % len(scale)],
                "intensity": round(0.6 + 0.4 * float(A_top), 3),
            })
        prev_side = side

    # Fallback: asegurar algo de textura ritmica si hubo pocas colisiones
    if len(events) < 6:
        for k in range(8):
            events.append({
                "frame": int(k * FRAMES / 8),
                "note": scale[k % len(scale)],
                "intensity": 0.8,
            })
        events.sort(key=lambda e: e["frame"])

    rows_idx = np.arange(H)
    for f in range(FRAMES):
        off = int(round(f * R / FRAMES)) % R
        idx = (off + rows_idx) % R
        Image.fromarray(master[idx], "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png")
        )
        if f % 60 == 0 or f == FRAMES - 1:
            print(f"[soliton] {f + 1}/{FRAMES}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[soliton] Eventos: {len(events)} -> {EVENTS_PATH}")
    print(f"[soliton] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
