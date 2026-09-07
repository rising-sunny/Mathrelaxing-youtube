"""
Short 9:16 — Arbol recursivo al atardecer (15s @ 60 fps, 1080x1920).

Pieza de ambiente: paleta calida, imagen figurativa y SIN overlay de formulas.
Es un registro distinto al resto del canal a proposito, asi que no pasa por
tools/latex_overlay.py; solo se le quema la marca y el CTA.

Todo el movimiento es periodico, asi que el loop cierra exacto.

Musica: la pista mas calma del catalogo, acorde al registro.
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_autumn"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "pillow_magic"
FRAMES = "900"
RES = "1920"
FPS = "60"


def main():
    music = find_track(MUSIC_TRACK)
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 arbol recursivo al atardecer ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080x1920 | loop exacto")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "autumn_tree.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16",
    ])
    if r.returncode != 0:
        sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME, "--skip-render",
        "--attractor", "clifford",   # perfil suave, sin percusion dura
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--format", "9:16", "--music", music,
    ])
    if r.returncode != 0:
        sys.exit("Error en build_clip.")

    # Sin overlay matematico: el registro de la pieza es ambiental, no didactico.
    branded = os.path.join(OUTDIR, f"{NAME}_branded.mp4")
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "tools", "brand_cta.py"),
        "-i", os.path.join(OUTDIR, f"{NAME}.mp4"), "-o", branded,
        "--cta-y", "0.885", "--handle-y", "0.030",
    ])
    if r.returncode != 0:
        sys.exit("Error quemando el CTA.")

    print(f"\n[{NAME}] LISTO -> {branded}")
    print(f"[{NAME}] Subir con: python upload_autumn_short.py")


if __name__ == "__main__":
    main()
