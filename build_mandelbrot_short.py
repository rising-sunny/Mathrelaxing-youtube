"""
Short 9:16 — Mandelbrot zoom infinito (15s @ 60 fps, 1080x1920).

Zoom exponencial 2.5e6x hacia el Valle de los Caballitos de Mar, terminando en
un mini-Mandelbrot (auto-similitud). Musica: drone theta hipnotico.
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_mandelbrot"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "new_beginning"
FRAMES = "900"
RES = "1920"
FPS = "60"


def main():
    music = find_track(MUSIC_TRACK)

    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 Mandelbrot zoom ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080x1920")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME,
        "--scene", "scenes/mandelbrot_zoom.py",
        "--attractor", "clifford",   # perfil de audio suave (no existe uno propio)
        "--engine", "numpy",
        "--frames", FRAMES,
        "--res", RES,
        "--fps", FPS,
        "--format", "9:16",
        "--music", music,
    ])
    if r.returncode != 0:
        sys.exit("Error en build_clip.")

    print(f"\n[{NAME}] LISTO -> {os.path.join(OUTDIR, f'{NAME}.mp4')}")


if __name__ == "__main__":
    main()
