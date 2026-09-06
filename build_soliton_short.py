"""
Short 9:16 — Solitones KdV (diagrama espacio-tiempo, 15s @ 60 fps, 1080x1920).

Tres solitones de distinta amplitud viajan a distinta velocidad y se cruzan
preservando su forma. Loop exacto por construccion (ver scenes/soliton_field.py).

Musica: drone calmo (misma familia ambiente del canal).
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_soliton"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "enlightened_drift"
FRAMES = "900"
RES = "1920"
FPS = "60"


def main():
    music = find_track(MUSIC_TRACK)

    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 Solitones KdV ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080x1920")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME,
        # v2: simulacion KdV en vivo (soliton_kdv.py), reemplaza al diagrama
        # espacio-tiempo estatico de soliton_field.py que quedo corto de
        # dinamismo (feedback del 2026-07-19).
        "--scene", "scenes/soliton_kdv.py",
        # --attractor solo elige el PERFIL DE AUDIO. No existe uno "soliton";
        # usamos "clifford" (suave), que ya se probo con la escena de Julia.
        "--attractor", "clifford",
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
