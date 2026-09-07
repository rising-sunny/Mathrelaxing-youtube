"""
Short 9:16 — Teorema de la bola peluda (15s @ 60 fps, 1080x1920).

Un campo vectorial tangente sobre la esfera, peinado con 22.000 lineas de
flujo. El campo se anula en los dos polos, y eso es inevitable: todo campo
tangente y continuo sobre S^2 tiene al menos un cero.

Loop exacto por doble periodicidad: el destello recorre una linea entera y la
esfera gira 2*pi, ambos en el mismo ciclo de 900 frames.

Musica: drone theta, la familia mas hipnotica del catalogo.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_hairyball"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "new_beginning"
FRAMES = "900"
RES = "1920"
FPS = "60"

THEOREM = r"$\mathbf{v}\ \mathrm{tangent\ on}\ \mathbb{S}^2 \ \Longrightarrow\ \exists\, \mathbf{p}:\ \mathbf{v}(\mathbf{p}) = \mathbf{0}$"
# Poincare-Hopf: la suma de indices de los ceros es la caracteristica de Euler,
# que para la esfera vale 2. De ahi que los ceros no se puedan eliminar.
EULER = r"$\sum \mathrm{index} = \chi(\mathbb{S}^2) = 2$"
LEGEND = r"$\mathrm{gold} = \mathrm{slow} \quad \mathrm{cyan} = \mathrm{fast}$"


def overlay_spec():
    frames = int(FRAMES)
    texts = [rf"$\theta = {360.0 * f / frames:5.1f}^\circ$" for f in range(frames)]
    return {
        "scrim": {"rgb": [9, 12, 30],
                  "top": {"extent": 0.26, "strength": 0.92},
                  "bottom": {"extent": 0.20, "strength": 0.88}},
        "static": [
            {"text": THEOREM, "y": 0.926, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 24},
            {"text": EULER,   "y": 0.882, "rgba": [0.45, 0.95, 1.0, 0.92], "size": 27},
            {"text": LEGEND,  "y": 0.845, "rgba": [1.0, 0.84, 0.42, 0.85], "size": 19},
        ],
        "dynamic": {"y": 0.806, "rgba": [1.0, 0.86, 0.42, 0.95], "size": 25,
                    "texts": texts},
    }


def main():
    music = find_track(MUSIC_TRACK)
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 teorema de la bola peluda ===")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "hairy_ball.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16",
    ])
    if r.returncode != 0:
        sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME, "--skip-render", "--attractor", "hopf",
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
    print(f"[{NAME}] Subir con: python upload_hairyball_short.py")


if __name__ == "__main__":
    main()
