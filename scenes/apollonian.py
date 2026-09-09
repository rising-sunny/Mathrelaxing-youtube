"""Empaquetamiento apolineo: un teorema sobre ENTEROS, dibujado.

Tres circunferencias tangentes entre si dejan dos huecos, y en cada uno cabe
exactamente una circunferencia tangente a las tres. Repetir para siempre da el
empaquetamiento apolineo.

Cual es esa cuarta circunferencia lo dice el teorema de Descartes, en terminos
de curvaturas k = 1/r:

    (k1 + k2 + k3 + k4)^2 = 2 (k1^2 + k2^2 + k3^2 + k4^2)

que despejado da  k4 = k1+k2+k3 +- 2*sqrt(k1k2 + k2k3 + k3k1). La version
COMPLEJA de la misma identidad, con z*k en lugar de k, entrega ademas el centro,
asi que una sola formula genera todo el dibujo.

Lo notable: si se arranca con curvaturas enteras que cumplan la identidad, la
raiz cuadrada se cancela en cada paso y TODAS las curvaturas del empaquetamiento
son enteras. Aca se arranca con (-1, 2, 2, 3): la de curvatura -1 es la
exterior, negativa porque contiene a las demas.

Es un tipo de expresion distinto al resto del canal: no una ecuacion de
evolucion sino una identidad algebraica, y su contenido es aritmetico.

    python scenes/apollonian.py -- --frames 900 --res 1920 --name shorts_apollonian --format 9:16
Escribe output/<name>/frames/%04d.png y data/<name>_events.json
"""

import json
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
NAME = arg("--name", "shorts_apollonian")
FMT = arg("--format", "9:16")
FPS = int(arg("--fps", 60))
KMAX = float(arg("--kmax", 900.0))      # curvatura maxima: radio minimo visible
SS = int(arg("--ss", 2))                # supermuestreo (PIL no antialiasa)
FILL = float(arg("--fill", 0.468))
HOLD = int(arg("--hold", 90))
LABELS = int(arg("--labels", 13))       # cuantas curvaturas se rotulan

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

BG = (10, 13, 30)
BIG = np.array([1.00, 0.80, 0.30])      # curvatura chica: oro
SMALL = np.array([0.32, 0.90, 1.00])    # curvatura grande: cian


def generate():
    """Todas las circunferencias con curvatura <= KMAX.

    Descartes da dos soluciones para la cuarta circunferencia y una de ellas es
    la que ya estaba. Restando las dos ecuaciones se cancela la raiz cuadrada:

        k4' = 2 (k1 + k2 + k3) - k4        (y lo mismo con b = z*k)

    Asi cada cuadrupla engendra EXACTAMENTE cuatro hijas, una por circulo
    reemplazado. Es un arbol, no una busqueda: la version con raices generaba
    duplicados y la expansion no terminaba nunca. Ademas, al quedar solo sumas
    y restas, unas curvaturas enteras siguen siendo enteras para siempre, que
    es justamente lo que el video muestra.
    """
    seed = [(-1.0, 0j), (2.0, -0.5 + 0j), (2.0, 0.5 + 0j), (3.0, (2.0 / 3.0) * 1j)]
    circles = {}

    def key(k, z):
        return (round(k, 4), round(z.real, 5), round(z.imag, 5))

    for k, z in seed:
        circles[key(k, z)] = (k, z)

    stack = [tuple(seed)]
    while stack:
        quad = stack.pop()
        for drop in range(4):
            others = [quad[i] for i in range(4) if i != drop]
            k_old, z_old = quad[drop]
            k_new = 2.0 * sum(c[0] for c in others) - k_old
            b_new = 2.0 * sum(c[0] * c[1] for c in others) - k_old * z_old
            if k_new <= 0 or k_new > KMAX:
                continue
            z_new = b_new / k_new
            kk = key(k_new, z_new)
            if kk in circles:
                continue
            circles[kk] = (k_new, z_new)
            stack.append(tuple(others) + ((k_new, z_new),))
    return sorted(circles.values(), key=lambda c: abs(c[0]))


def main():
    circles = generate()
    ks = np.array([c[0] for c in circles])
    ints = np.abs(ks - np.round(ks))
    print(f"[apollo] {len(circles)} circunferencias | curvaturas hasta {ks.max():.0f}")
    print(f"[apollo] desviacion maxima respecto del entero mas cercano: {ints.max():.2e}")

    scale = W * FILL * SS
    cx, cy = W * SS * 0.5, H * SS * 0.5
    fnt = None
    fp = font_path("bold")
    scale_note = ["C2", "Eb2", "G2", "Bb2", "C3", "Eb3", "G3", "Bb3"]
    events = []
    reveal = max(1, FRAMES - HOLD)

    for f in range(FRAMES):
        p = min(1.0, (f + 1) / reveal)
        n = max(4, int(len(circles) * p ** 1.7))       # aparecen de mayor a menor
        img = Image.new("RGB", (W * SS, H * SS), BG)
        dr = ImageDraw.Draw(img)
        for i, (k, z) in enumerate(circles[:n]):
            r = abs(1.0 / k) * scale
            x, y = z.real * scale + cx, -z.imag * scale + cy
            # escala log entre k=2 (oro) y KMAX (cian): con log1p desde 0
            # casi todo caia en el extremo calido
            t = float(np.clip((np.log(max(abs(k), 2.0)) - np.log(2.0))
                              / (np.log(KMAX) - np.log(2.0)), 0.0, 1.0))
            col = tuple(int(255 * c) for c in (BIG * (1 - t) + SMALL * t))
            lw = max(SS, int(round(r * 0.055)))
            dr.ellipse([x - r, y - r, x + r, y + r], outline=col, width=lw)
            # las mayores llevan su curvatura: es el punto del video
            if i < LABELS and r > 26 * SS and k > 0:
                if fnt is None or getattr(fnt, "_r", None) != int(r):
                    fnt = ImageFont.truetype(fp, max(12, int(r * 0.42))) if fp else ImageFont.load_default()
                    fnt._r = int(r)
                s = str(int(round(k)))
                bb = dr.textbbox((0, 0), s, font=fnt)
                dr.text((x - (bb[2] - bb[0]) / 2, y - (bb[3] - bb[1]) / 2 - bb[1]),
                        s, font=fnt, fill=col)

        small = img.resize((W, H), Image.LANCZOS)
        a = np.asarray(small).astype(np.float32) / 255.0
        a = np.clip(a + 0.40 * gaussian_filter(a, (2.2, 2.2, 0)), 0, 1)
        Image.fromarray((a * 255).astype(np.uint8), "RGB").save(
            os.path.join(FRAMES_DIR, f"{f:04d}.png"))

        if f % max(1, FRAMES // 8) == 0:
            events.append({"frame": f, "note": scale_note[len(events) % 8],
                           "intensity": 0.75})
        if f % 100 == 0 or f == FRAMES - 1:
            print(f"[apollo] {f + 1}/{FRAMES}  {n} circunferencias")

    with open(EVENTS_PATH, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": FRAMES / FPS, "fps": FPS, "events": events}, jf)
    print(f"[apollo] Done! {FRAMES} frames -> {FRAMES_DIR}")


if __name__ == "__main__":
    main()
