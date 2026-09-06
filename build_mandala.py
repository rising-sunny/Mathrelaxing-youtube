"""
build_mandala.py — Orquestador del mandala de Chladni SIN Blender.

Cadena: render rapido numpy/PIL (chladni_mandala_fast.py) -> audio + overlay
matematico + mux con ducking (render/build_clip.py). Termina en minutos.

    python build_mandala.py
    python build_mandala.py --music data/mandala_music.mp3   # pista externa (ej. Epidemic Sound) en vez del drone
"""
import argparse
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
NAME = "shorts_mandala"
FRAMES = 900


def run(cmd):
    print("›", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=REPO)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--music", type=str, default=None, help="Ruta a una pista musical externa (mp3/wav)")
    ap.add_argument("--skip-render", action="store_true", help="Reusa los frames ya generados")
    a = ap.parse_args()

    if not a.skip_render:
        run([
            sys.executable, "scenes/chladni_mandala_fast.py",
            "--frames", str(FRAMES), "--res", "1024", "--format", "9:16", "--name", NAME,
        ])

    clip_cmd = [
        sys.executable, "render/build_clip.py",
        "--name", NAME, "--skip-render",
        "--frames", str(FRAMES), "--res", "1024", "--format", "9:16",
        "--math-overlay", "--waveform",
        "--attractor", "chladni_melody", "--fps", "60",
    ]
    if a.music:
        clip_cmd += ["--music", a.music]
    run(clip_cmd)
    print("TODO LISTO!")


if __name__ == "__main__":
    main()
