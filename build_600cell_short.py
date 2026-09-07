"""
Short 9:16 — 600-cell, el politopo regular de 4D (15s @ 60 fps, 1080x1920).

120 vertices sobre la 3-esfera, 720 aristas, 600 celdas tetraedricas. Rotacion
isoclina de 0 a 2pi: el loop cierra exacto. Proyeccion estereografica desde
S^3, que es lo que curva las aristas en arcos.

Musica: la misma pista del short de Clifford, su pariente mas cercano.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_600cell"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "betawaves"
FRAMES = "900"
RES = "1920"
FPS = "60"

# Simbolo de Schlafli, el censo de caras y la proyeccion. Todo por encima de
# 0.80: la banda de abajo queda libre para el CTA.
SCHLAFLI = r"$\{3,3,5\} \subset \mathbb{S}^3 \subset \mathbb{R}^4$"
CENSUS = r"$120\ \mathrm{vertices} \quad 720\ \mathrm{edges} \quad 600\ \mathrm{cells}$"
PROJECTION = r"$\pi(x,y,z,w) = (x,y,z)/(1-w) \quad \mathrm{(stereographic)}$"


def overlay_spec():
    """El angulo mostrado es el de la rotacion isoclina de la escena."""
    frames = int(FRAMES)
    texts = [rf"$\theta = {360.0 * f / frames:5.1f}^\circ$" for f in range(frames)]
    return {
        # La escena llena el cuadro: sin el degradado, las formulas compiten
        # con los arcos. Abajo tambien, que ahi va el CTA.
        "scrim": {"rgb": [10, 13, 32],
                  "top": {"extent": 0.26, "strength": 0.92},
                  "bottom": {"extent": 0.20, "strength": 0.88}},
        "static": [
            {"text": CENSUS,     "y": 0.925, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 27},
            {"text": SCHLAFLI,   "y": 0.884, "rgba": [1.0, 0.90, 0.55, 0.90], "size": 28},
            {"text": PROJECTION, "y": 0.846, "rgba": [0.66, 0.80, 1.0, 0.85], "size": 20},
        ],
        "dynamic": {"y": 0.806, "rgba": [1.0, 0.86, 0.42, 0.95], "size": 25,
                    "texts": texts},
    }


def main():
    music = find_track(MUSIC_TRACK)
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 600-cell (politopo 4D) ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080x1920 | loop exacto")

    # 1) Escena
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "cell600_4d.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16",
    ])
    if r.returncode != 0:
        sys.exit("Error renderizando la escena.")

    # 2) Audio + mux sobre los frames ya escritos
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME, "--skip-render",
        "--attractor", "hopf",      # el movimiento va por fibras de Hopf
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--format", "9:16", "--music", music,
    ])
    if r.returncode != 0:
        sys.exit("Error en build_clip.")

    # 3) Overlay matematico
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

    # 4) CTA de suscripcion
    branded = os.path.join(OUTDIR, f"{NAME}_branded.mp4")
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "tools", "brand_cta.py"),
        "-i", with_math, "-o", branded,
        "--cta-y", "0.795", "--handle-y", "0.028",
    ])
    if r.returncode != 0:
        sys.exit("Error quemando el CTA.")

    print(f"\n[{NAME}] LISTO -> {branded}")
    print(f"[{NAME}] Subir con: python upload_600cell_short.py")


if __name__ == "__main__":
    main()
