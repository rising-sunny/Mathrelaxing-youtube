"""
Short 9:16 — Buddhabrot (15s @ 60 fps, 1080x1920).

La cara oculta del conjunto de Mandelbrot: en vez de pintar QUE puntos escapan,
se pinta POR DONDE PASAN los que escapan. La figura emerge de la nada a medida
que se acumulan las orbitas.

Musica: drone theta, la misma familia de los otros fractales del canal.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_buddhabrot"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "new_beginning"
FRAMES = "900"
RES = "1920"
FPS = "60"
BATCH = "10000"

ITER = r"$z_{n+1} = z_n^{2} + c \qquad z_0 = 0$"
RULE = r"$\mathrm{if}\ |z_n| \to \infty,\ \mathrm{record\ every}\ z_n$"
LEGEND = r"$\mathrm{red}: 5000\ \mathrm{iterations} \quad \mathrm{blue}: 50$"


def overlay_spec():
    frames = int(FRAMES)
    per = int(BATCH)
    texts = []
    for f in range(frames):
        n = (f + 1) * per
        digits = f"{n:,}".replace(",", r"\,")     # separador fino, estilo ISO
        texts.append(rf"${digits}\ \mathrm{{orbits}}$")
    return {
        "scrim": {"rgb": [8, 10, 26],
                  "top": {"extent": 0.26, "strength": 0.92},
                  "bottom": {"extent": 0.20, "strength": 0.88}},
        "static": [
            {"text": ITER,   "y": 0.926, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 29},
            {"text": RULE,   "y": 0.882, "rgba": [1.0, 0.86, 0.45, 0.92], "size": 22},
            {"text": LEGEND, "y": 0.845, "rgba": [0.66, 0.80, 1.0, 0.82], "size": 19},
        ],
        "dynamic": {"y": 0.806, "rgba": [1.0, 0.86, 0.42, 0.95], "size": 25,
                    "texts": texts},
    }


def main():
    music = find_track(MUSIC_TRACK)
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 Buddhabrot ===")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "buddhabrot.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16", "--batch", BATCH,
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
    print(f"[{NAME}] Subir con: python upload_buddhabrot_short.py")


if __name__ == "__main__":
    main()
