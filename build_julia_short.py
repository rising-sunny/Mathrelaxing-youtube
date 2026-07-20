"""
Short 9:16 — Julia set morph (15s @ 60 fps, 1080×1920).

El parametro c recorre un circulo cerrado, asi que el fractal se deforma y
vuelve al punto de partida: loop sin corte.

Musica: drone theta (hipnotico, encaja con el morph continuo).
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
NAME = "shorts_julia"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC = r"C:\Users\sunse\Downloads\ES_A New Beginning (Theta Drone L216Hz R220Hz) - Bruce Brus.wav"
FRAMES = "900"   # 15 s @ 60 fps
RES = "1920"     # altura → 1080×1920 en 9:16
FPS = "60"


def main():
    if not os.path.isfile(MUSIC):
        sys.exit(f"No se encontró la pista: {MUSIC}")

    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 Julia morph ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080×1920 | music={os.path.basename(MUSIC)}")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME,
        "--scene", "scenes/julia_morph.py",
        # OJO: --attractor solo elige el PERFIL DE AUDIO en audio/build_audio.py,
        # no los visuales (esos salen de --scene). No existe un perfil "julia" y
        # la cadena de build_audio no tiene else final, asi que un valor nuevo
        # reventaria. Usamos "clifford": suave y geometrico, encaja con el morph.
        "--attractor", "clifford",
        "--engine", "numpy",
        "--frames", FRAMES,
        "--res", RES,
        "--fps", FPS,
        "--format", "9:16",
        "--music", MUSIC,
    ])
    if r.returncode != 0:
        sys.exit("Error en build_clip.")

    final = os.path.join(OUTDIR, f"{NAME}.mp4")
    print(f"\n[{NAME}] LISTO -> {final}")


if __name__ == "__main__":
    main()
