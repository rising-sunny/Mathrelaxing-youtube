"""
Short 9:16 — Three-Body Figure-8 (15s @ 60 fps, 1080×1920).

Música: misma playlist Epidemic Sound (recorte de la primera pista).
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_threebody"
OUTDIR = os.path.join(REPO, "output", NAME)

# Preferimos un tramo limpio de Betawaves (focus) — corta a 15s en build_clip
MUSIC_TRACK = "betawaves"
FRAMES = "900"   # 15 s @ 60 fps
RES = "1920"     # altura → 1080×1920 en 9:16
FPS = "60"


def main():
    music = find_track(MUSIC_TRACK)

    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 Three-Body Figure-8 ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080×1920 | music={os.path.basename(music)}")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME,
        "--scene", "scenes/threebody_1h_numpy.py",
        "--attractor", "threebody",
        "--engine", "numpy",
        "--frames", FRAMES,
        "--res", RES,
        "--fps", FPS,
        "--format", "9:16",
        "--music", music,
    ])
    if r.returncode != 0:
        sys.exit("Error en build_clip.")

    final = os.path.join(OUTDIR, f"{NAME}.mp4")
    print(f"\n[{NAME}] LISTO -> {final}")


if __name__ == "__main__":
    main()
