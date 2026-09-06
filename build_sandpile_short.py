"""
Short 9:16 — Pila de arena abeliana (15s @ 60 fps, 1080x1920).

Un millon de granos sobre una sola celda. Regla unica: 4 granos colapsan y
reparten uno a cada vecino. El estado final es unico (teorema abeliano) y es
un fractal. La camara sigue el radio de la pila, asi que el tamano aparente
queda fijo y lo que se ve es la estructura refinandose a toda escala.

Musica: drone calmo, la misma familia ambiente del canal.
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_sandpile"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "enlightened_drift"
GRAINS = "500000"
FRAMES = "900"
RES = "1920"
FPS = "60"


def main():
    music = find_track(MUSIC_TRACK)

    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 Pila de arena abeliana ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080x1920 | {int(GRAINS):,} granos")

    # La escena acepta --grains, que build_clip no reenvia: se renderiza aparte
    # y build_clip solo arma audio + mux sobre los frames ya escritos.
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "abelian_sandpile.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16", "--grains", GRAINS,
    ])
    if r.returncode != 0:
        sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME,
        "--skip-render",
        "--attractor", "chladni",   # resonancia de placa: el perfil mas cercano a la arena
        "--frames", FRAMES,
        "--res", RES,
        "--fps", FPS,
        "--format", "9:16",
        "--music", music,
    ])
    if r.returncode != 0:
        sys.exit("Error en build_clip.")

    print(f"\n[{NAME}] LISTO -> {os.path.join(OUTDIR, f'{NAME}.mp4')}")
    print(f"[{NAME}] Falta el CTA en pantalla:")
    print(f"[{NAME}]   python tools/brand_cta.py -i output/{NAME}/{NAME}.mp4")


if __name__ == "__main__":
    main()
