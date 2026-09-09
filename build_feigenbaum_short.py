"""
Short 9:16 — Diagrama de bifurcacion y la constante de Feigenbaum (15s @ 60 fps).

Zoom hacia el punto de acumulacion de la cascada de duplicaciones de periodo.
La ventana se encoge por delta en r y por alpha en x, que son las dos razones
de Feigenbaum.

NO es un loop: la autosemejanza vale para la estructura local de la cascada, no
reproduce el cuadro entero a escala (medido: correlacion 0,14 entre el primer
frame y el que cerraria el ciclo).

Musica: drone theta, la familia hipnotica del catalogo.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_feigenbaum"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "new_beginning"
FRAMES = "900"
RES = "1920"
FPS = "60"
DELTA = 4.6692016091029907
DOUBLINGS = 5.5

MAP = r"$x_{n+1} = r\,x_n(1 - x_n)$"
FEIGEN = r"$\delta = 4.669\,201\,609\ldots$"
UNIVERSAL = r"$\mathrm{the\ same}\ \delta\ \mathrm{for\ every\ unimodal\ map}$"


def overlay_spec():
    frames = int(FRAMES)
    texts = []
    for f in range(frames):
        z = DELTA ** (DOUBLINGS * f / frames)
        texts.append(rf"$\mathrm{{zoom}} \times {z:,.0f}$".replace(",", r"\,")
                     if z >= 10 else rf"$\mathrm{{zoom}} \times {z:.1f}$")
    return {
        "scrim": {"rgb": [9, 12, 30],
                  "top": {"extent": 0.26, "strength": 0.92},
                  "bottom": {"extent": 0.20, "strength": 0.88}},
        "static": [
            {"text": MAP,       "y": 0.926, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 29},
            {"text": FEIGEN,    "y": 0.882, "rgba": [1.0, 0.86, 0.42, 0.94], "size": 26},
            {"text": UNIVERSAL, "y": 0.845, "rgba": [0.55, 0.88, 1.0, 0.85], "size": 19},
        ],
        "dynamic": {"y": 0.806, "rgba": [0.55, 0.92, 1.0, 0.95], "size": 25,
                    "texts": texts},
    }


def main():
    music = find_track(MUSIC_TRACK)
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 bifurcacion / Feigenbaum ===")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "bifurcation_zoom.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16", "--doublings", str(DOUBLINGS),
    ])
    if r.returncode != 0:
        sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME, "--skip-render", "--attractor", "clifford",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--format", "9:16", "--music", music,
    ])
    if r.returncode != 0:
        sys.exit("Error en build_clip.")

    overlay_dir = os.path.join(OUTDIR, "overlay")
    spec_path = os.path.join(OUTDIR, "overlay_spec.json")
    with open(spec_path, "w", encoding="utf-8") as fh:
        json.dump(overlay_spec(), fh)
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "tools", "latex_overlay.py"),
        "--spec", spec_path, "--outdir", overlay_dir,
        "--res-w", "1080", "--res-h", "1920",
    ])
    if r.returncode != 0:
        sys.exit("Error generando el overlay matematico.")

    clip = os.path.join(OUTDIR, f"{NAME}.mp4")
    with_math = os.path.join(OUTDIR, f"{NAME}_math.mp4")
    r = subprocess.run([
        "ffmpeg", "-y", "-i", clip, "-framerate", FPS,
        "-i", os.path.join(overlay_dir, "%04d.png"),
        "-filter_complex", "[0:v][1:v]overlay=0:0[v]", "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "copy", with_math,
    ])
    if r.returncode != 0:
        sys.exit("Error componiendo el overlay.")

    branded = os.path.join(OUTDIR, f"{NAME}_branded.mp4")
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "tools", "brand_cta.py"),
        "-i", with_math, "-o", branded, "--cta-y", "0.795", "--handle-y", "0.028",
    ])
    if r.returncode != 0:
        sys.exit("Error quemando el CTA.")

    print(f"\n[{NAME}] LISTO -> {branded}")
    print(f"[{NAME}] Subir con: python upload_feigenbaum_short.py")


if __name__ == "__main__":
    main()
