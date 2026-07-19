"""
build_slice.py — Orquestador del vertical slice MathRelaxing (local).

Ejecuta la cadena completa:
  render headless (Blender) -> audio (drone + hits) -> mux con ducking (FFmpeg)
y produce output/slice/slice.mp4

    python render/build_slice.py                          # todo, valores por defecto
    python render/build_slice.py --skip-render            # reusa los frames ya renderizados
    python render/build_slice.py --frames 72 --res 360 --samples 24 --engine cycles
"""

import argparse
import glob
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "output", "slice")
FRAMES_DIR = os.path.join(OUT, "frames")


def find_blender():
    hits = glob.glob(os.path.join(REPO, "tools", "blender", "**", "blender.exe"), recursive=True)
    if not hits:
        sys.exit("No se encontró blender.exe en tools/blender/. Revisa la instalación portable.")
    return hits[0]


def run(cmd):
    print("›", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--frames", default="72")
    ap.add_argument("--res", default="360")
    ap.add_argument("--samples", default="24")
    ap.add_argument("--engine", default="cycles")
    ap.add_argument("--fps", default="24")
    a = ap.parse_args()

    # 1) Render headless de la escena paramétrica
    if not a.skip_render:
        run([find_blender(), "--background", "--python",
             os.path.join(REPO, "scenes", "slice_field.py"), "--",
             "--engine", a.engine, "--frames", a.frames, "--res", a.res, "--samples", a.samples])

    # 2) Audio: drone (Do menor) + hits (sonificación)
    run([sys.executable, os.path.join(REPO, "audio", "build_audio.py")])

    # 3) Frames -> video silencioso
    video = os.path.join(OUT, "video_silent.mp4")
    run(["ffmpeg", "-y", "-framerate", a.fps, "-i", os.path.join(FRAMES_DIR, "%04d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", video])

    # 4) Drone "ducked" por los hits (sidechain) + mezcla de ambas pistas
    amix = os.path.join(OUT, "audio_mix.wav")
    flt = ("[0:a][1:a]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[duck];"
           "[duck][1:a]amix=inputs=2:duration=longest:weights=1 1.3[mix]")
    run(["ffmpeg", "-y", "-i", os.path.join(OUT, "drone.wav"), "-i", os.path.join(OUT, "hits.wav"),
         "-filter_complex", flt, "-map", "[mix]", amix])

    # 5) Video + audio -> slice final
    final = os.path.join(OUT, "slice.mp4")
    run(["ffmpeg", "-y", "-i", video, "-i", amix, "-c:v", "copy", "-c:a", "aac",
         "-b:a", "192k", "-shortest", final])

    print(f"\n[slice] LISTO -> {final}")


if __name__ == "__main__":
    main()
