"""Teorema de las tres distancias (Steinhaus).

Se toman los puntos {alpha}, {2 alpha}, ..., {N alpha} sobre el circulo de
perimetro 1 y se miran los huecos que dejan. El teorema dice que esos huecos
tienen como mucho TRES longitudes distintas, para cualquier alpha y cualquier
N. Y cuando hay tres, la mayor es exactamente la suma de las otras dos.

No es "casi tres" ni "tres en promedio": son tres, siempre. Verificado al
arrancar la escena sobre la propia alpha del clip.

La escena es una cascada: la fila N es el intervalo cortado por esos N puntos,
con cada hueco pintado segun a cual de las tres longitudes pertenece. Se ven
SIEMPRE todas las filas desde N=1, reescaladas para llenar la banda, asi que
la imagen no repite nada: empieza en tres franjas gruesas y termina en un
tejido de cientos de filas.

    python scenes/three_distance.py -- --frames 900 --res 1920 --name shorts_three --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


FRAMES = int(arg("--frames", 900))
RES = int(arg("--res", 1920))
NAME = arg("--name", "shorts_three")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
NMAX = int(arg("--nmax", 520))
EASE = float(arg("--ease", 1.8))        # >1: arranca lento, se acelera
ALPHA = float(arg("--alpha", (math.sqrt(5) - 1) / 2))   # 1/phi
HOLD = int(arg("--hold", 60))

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

# corta, media, larga. Apagadas a proposito: a plena saturacion la banda
# llena el cuadro de amarillo y magenta neon y es insoportable en un telefono,
# ademas de no parecerse en nada al resto del canal.
CLASS_COL = np.array([[0.13, 0.44, 0.60],
                      [0.46, 0.17, 0.42],
                      [0.62, 0.42, 0.14]], dtype=np.float32)


def row_data(alpha, n, tol=1e-9):
    """Puntos, longitudes distintas y la clase de cada hueco, para la fila n."""
    pts = np.sort(((np.arange(1, n + 1) * alpha) % 1.0))
    edges = np.concatenate([[0.0], pts, [1.0]])
    g = np.diff(edges)
    keep = g > tol
    g = g[keep]
    lo = np.concatenate([[0.0], pts])[keep]
    uniq = []
    for v in np.sort(g):
        if not uniq or abs(v - uniq[-1]) > 1e-7:
            uniq.append(v)
    uniq = np.array(uniq)
    cls = np.abs(g[:, None] - uniq[None, :]).argmin(axis=1)
    if len(uniq) == 2:                      # sin clase intermedia: corta y larga
        cls = np.where(cls == 1, 2, 0)
    elif len(uniq) == 1:
        cls = np.zeros_like(cls)
    return lo, g, uniq, cls


def main():
    # --- el teorema, comprobado sobre la alpha de este clip ----------------
    counts, bad = [], 0
    for n in range(1, NMAX + 1):
        _, _, uniq, _ = row_data(ALPHA, n)
        counts.append(len(uniq))
        if len(uniq) == 3 and abs(uniq[2] - (uniq[0] + uniq[1])) > 1e-7:
            bad += 1
    counts = np.array(counts)
    assert counts.max() <= 3, f"aparecieron {counts.max()} longitudes distintas"
    assert bad == 0, f"{bad} filas donde la mayor no es la suma de las otras dos"
    print(f"[3d] alpha = {ALPHA:.12f}")
    print(f"[3d] N=1..{NMAX}: longitudes distintas maximo {counts.max()}, "
          f"minimo {counts.min()}  (3 en {int((counts==3).sum())} filas, "
          f"2 en {int((counts==2).sum())})")
    print(f"[3d] filas con 3 longitudes donde la mayor NO es la suma: {bad}")

    # --- cada fila se rasteriza UNA vez a un vector de ancho W -------------
    xs = (np.arange(W) + 0.5) / W
    rows = np.zeros((NMAX, W, 3), dtype=np.uint8)
    per_row = []
    for n in range(1, NMAX + 1):
        lo, g, uniq, cls = row_data(ALPHA, n)
        idx = np.clip(np.searchsorted(lo, xs, side="right") - 1, 0, len(lo) - 1)
        rows[n - 1] = (CLASS_COL[cls[idx]] * 255).astype(np.uint8)
        per_row.append((len(uniq), uniq.tolist()))
    print(f"[3d] {NMAX} filas rasterizadas")

    mx = int(0.055 * W)                   # aire oscuro a los costados
    band_y0 = int(0.300 * H)
    band_y1 = int(0.775 * H)
    band_h = band_y1 - band_y0
    cur_y0 = int(0.246 * H)
    cur_h = int(0.040 * H)

    fp = font_path("bold")
    fnt = ImageFont.truetype(fp, int(0.023 * W)) if fp else ImageFont.load_default()

    reveal = max(1, FRAMES - HOLD)
    scale_note = ["D3", "A3", "D4", "F4", "A4", "C5", "D5", "F5"]
    events, shown = [], []

    for f in range(FRAMES):
        p = min(1.0, (f + 1) / reveal)
        n = max(1, int(round(1 + (NMAX - 1) * p ** EASE)))
        shown.append(n)

        img = np.zeros((H, W, 3), dtype=np.float32)
        # la banda muestra SIEMPRE las filas 1..n, estiradas a su alto: la
        # imagen se comprime en vez de llenarse, y no deja de transformarse
        bw = W - 2 * mx
        block = Image.fromarray(rows[:n]).resize((bw, band_h), Image.NEAREST)
        img[band_y0:band_y1, mx:mx + bw] = np.asarray(block).astype(np.float32) / 255.0

        # la fila actual, ampliada arriba, con los puntos marcados
        cur = Image.fromarray(rows[n - 1:n]).resize((bw, cur_h), Image.NEAREST)
        img[cur_y0:cur_y0 + cur_h, mx:mx + bw] = np.asarray(cur).astype(np.float32) / 255.0

        pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
        dr = ImageDraw.Draw(pil)
        pts = np.sort(((np.arange(1, n + 1) * ALPHA) % 1.0))
        if n <= 160:
            for q in pts:
                x = mx + q * bw
                dr.line([(x, cur_y0), (x, cur_y0 + cur_h)], fill=(6, 7, 18),
                        width=max(1, int(0.0022 * W)))
        dr.rectangle([mx, cur_y0, mx + bw - 1, cur_y0 + cur_h],
                     outline=(118, 130, 168))
        dr.rectangle([mx, band_y0, mx + bw - 1, band_y1 - 1], outline=(62, 72, 102))
        dr.text((W / 2, cur_y0 - 0.026 * H), f"N = {n}", font=fnt,
                fill=(190, 200, 230), anchor="mm")

        a = np.asarray(pil).astype(np.float32) / 255.0
        a = np.clip(a + 0.34 * gaussian_filter(a, (1.3, 1.3, 0)), 0.0, 1.0)
        Image.fromarray((a * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.8})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[3d] {f + 1}/{FRAMES}  N = {n}  "
                  f"longitudes {per_row[n - 1][0]}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events,
                   "alpha": ALPHA, "nmax": NMAX, "shown": shown,
                   "lengths": [per_row[i][0] for i in range(NMAX)],
                   "max_distinct": int(counts.max()),
                   "rows_with_three": int((counts == 3).sum())}, jf)
    print(f"[3d] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
