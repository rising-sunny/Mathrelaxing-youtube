"""Aurora boreal sobre un lago — pieza de ambiente, hermana fria del otono.

Las cortinas no son una textura de ruido: cada una es una curva cuyo eje se
desplaza con la altura y el tiempo, y el brillo cae con la distancia a ese eje.
Encima va el rayado vertical caracteristico, que en una aurora real son los
electrones bajando por las lineas del campo magnetico terrestre.

Todo el movimiento se arma con senoidales de frecuencia temporal ENTERA sobre
el ciclo, asi que la pieza es periodica por construccion y el loop cierra sin
crossfade: cortinas, rayado, titileo de estrellas y ondas del lago.

El lago no es un espejo plano: se muestrea el cielo ya dibujado, invertido,
comprimido y desplazado horizontalmente por una onda, que es lo que da la
lectura de agua en movimiento.

    python scenes/aurora_lake.py -- --frames 900 --res 1920 --name shorts_aurora --format 9:16
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
NAME = arg("--name", "shorts_aurora")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
SEED = int(arg("--seed", 4111))
HORIZON = float(arg("--horizon", 0.615))
EXPOSURE = float(arg("--exposure", 1.55))
GLOW = float(arg("--glow", 0.62))

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
HY = int(H * HORIZON)

# Cielo: indigo profundo arriba, algo mas claro contra el horizonte.
SKY_TOP = np.array([7, 10, 30], dtype=np.float64)
SKY_HOR = np.array([17, 26, 54], dtype=np.float64)
WATER = np.array([6, 9, 22], dtype=np.float64)
# La aurora cambia de color con la altura: verde abajo, turquesa, violeta arriba.
AUR_LO = np.array([0.30, 1.00, 0.52])
AUR_MID = np.array([0.32, 0.92, 0.86])
AUR_HI = np.array([0.62, 0.42, 0.95])

rng = np.random.default_rng(SEED)
N_CURTAIN = 6
CURTAINS = []
for k in range(N_CURTAIN):
    CURTAINS.append({
        "x0": (k + 0.5) / N_CURTAIN + rng.uniform(-0.07, 0.07),   # repartidas, no apiladas
        "wid": rng.uniform(0.026, 0.052),
        "amp": rng.uniform(0.025, 0.065),
        "gain": rng.uniform(0.75, 1.30),
        # frecuencias temporales ENTERAS: condicion para que el ciclo cierre
        "waves": [(rng.uniform(0.30, 1.05), int(rng.integers(1, 4)), rng.uniform(0, 6.28))
                  for _ in range(3)],
        "rayf": rng.uniform(4.0, 8.0),
        "raym": int(rng.integers(1, 3)),
        "rayp": rng.uniform(0, 6.28),
        "top": rng.uniform(0.72, 1.0),
    })

# Estrellas fijas, con titileo periodico
N_STARS = 320
ST_X = rng.uniform(0, 1, N_STARS)
ST_Y = rng.uniform(0, 0.92, N_STARS) * HORIZON
ST_B = rng.uniform(0.30, 1.0, N_STARS) ** 1.7
ST_M = rng.integers(1, 4, N_STARS)
ST_P = rng.uniform(0, 6.28, N_STARS)

# Silueta de montanas: suma de senoidales en x (estatica)
def ridge(nx, base, amp, seed, octaves=5):
    r = np.random.default_rng(seed)
    x = np.linspace(0, 1, nx)
    h = np.zeros(nx)
    for o in range(octaves):
        h += (amp / (1.7 ** o)) * np.sin(2 * np.pi * (1.5 * 1.9 ** o) * x + r.uniform(0, 6.28))
    return base + h


RIDGES = [
    (ridge(W, HORIZON - 0.085, 0.030, SEED + 1), np.array([16, 21, 44], dtype=np.float64)),
    (ridge(W, HORIZON - 0.030, 0.022, SEED + 2), np.array([9, 12, 27], dtype=np.float64)),
]

_yy, _xx = np.mgrid[0:HY, 0:W]
_XN = _xx / W
_H = (HY - _yy) / HY          # 0 en el horizonte, 1 arriba del cuadro


def sky_field(t):
    """Cielo + aurora, solo la banda de arriba del horizonte."""
    img = SKY_TOP[None, None, :] + (SKY_HOR - SKY_TOP)[None, None, :] * (1.0 - _H)[:, :, None]

    # estrellas (se apagan donde la aurora es intensa, se suman antes)
    star = np.zeros((HY, W))
    px = np.clip((ST_X * W).astype(int), 0, W - 1)
    py = np.clip((ST_Y / HORIZON * HY).astype(int), 0, HY - 1)
    tw = 0.65 + 0.35 * np.sin(2 * np.pi * ST_M * t + ST_P)
    np.add.at(star, (py, px), ST_B * tw * 255.0)
    star = gaussian_filter(star, 0.9)
    img += 1.5 * star[:, :, None] * np.array([0.85, 0.90, 1.0])[None, None, :]

    aur = np.zeros((HY, W))
    for c in CURTAINS:
        cx = np.full_like(_H, c["x0"])
        for (f, m, p) in c["waves"]:
            cx = cx + c["amp"] * np.sin(2 * np.pi * (f * _H + m * t) + p)
        wid = c["wid"] * (0.55 + 0.85 * _H)          # se abre hacia arriba
        d = (_XN - cx) / wid
        body = np.exp(-d * d)
        # rayado vertical: los electrones bajando por el campo magnetico
        ray = 0.76 + 0.24 * np.sin(2 * np.pi * (c["rayf"] * (_XN - cx) / c["wid"]
                                                + c["raym"] * t) + c["rayp"])
        # borde inferior neto y desvanecido hacia arriba, como en una aurora real
        env = (np.clip(1.0 - (_H / c["top"]) ** 1.8, 0.0, 1.0)
               * np.clip((_H - 0.11) / 0.09, 0.0, 1.0))
        aur += c["gain"] * body * ray * env
    return img, aur


def colorize(aur):
    """Verde abajo, turquesa al medio, violeta arriba."""
    lo = np.clip(_H * 2.2, 0.0, 1.0)[:, :, None]
    hi = np.clip(_H * 1.7 - 0.55, 0.0, 1.0)[:, :, None]
    col = AUR_LO[None, None, :] * (1 - lo) + AUR_MID[None, None, :] * lo
    col = col * (1 - hi) + AUR_HI[None, None, :] * hi
    return col * aur[:, :, None]


def main():
    print(f"[aurora] {FRAMES} frames | {W}x{H} | horizonte {HY}px | {N_CURTAIN} cortinas")
    scale_note = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3"]
    events = []
    lake_h = H - HY
    ly = np.arange(lake_h)[:, None]
    lx = np.arange(W)[None, :]

    for f in range(FRAMES):
        t = f / FRAMES                     # ciclo completo -> loop exacto
        base, aur = sky_field(t)
        lit = colorize(aur) * 255.0
        lit = lit + GLOW * gaussian_filter(lit, (3.4, 3.4, 0))
        sky = base + lit

        canvas = np.zeros((H, W, 3), dtype=np.float64)
        canvas[:HY] = sky

        # --- lago: el cielo invertido, comprimido y ondulado ---
        src_y = np.clip((HY - 1 - (ly * 0.88)).astype(int), 0, HY - 1)
        wob = (6.0 * np.sin(2 * np.pi * (ly / lake_h * 3.0 + 1 * t))
               + 3.0 * np.sin(2 * np.pi * (ly / lake_h * 7.0 - 2 * t))).astype(int)
        src_x = np.clip(lx + wob, 0, W - 1)
        refl = sky[src_y, src_x]
        depth = np.clip(ly / lake_h, 0, 1)[:, :, None]
        canvas[HY:] = WATER[None, None, :] + (refl - WATER[None, None, :]) * (0.46 * (1 - depth * 0.75))

        # --- montanas, por encima del cielo y del reflejo ---
        for hcurve, col in RIDGES:
            ytop = (hcurve * H).astype(int)
            mask = np.arange(H)[:, None] >= ytop[None, :]
            mask[HY:, :] = False           # no tapan el agua
            canvas[mask] = col

        rgb = 1.0 - np.exp(-EXPOSURE * canvas / 255.0)
        Image.fromarray(np.clip(rgb * 255.0, 0, 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.5})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[aurora] {f + 1}/{FRAMES}")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[aurora] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
