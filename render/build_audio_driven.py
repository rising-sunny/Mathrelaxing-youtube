"""
build_audio_driven.py — Orquestador para simulaciones controladas por audio.

Cadena: render headless (Blender) -> mux con audio original (FFmpeg).
Produce output/<name>/<name>.mp4

    python render/build_audio_driven.py --name chladni_music --scene scenes/chladni_audio_driven.py \
        --input-audio data/input_music.mp3 --frames 7336
"""

import argparse
import glob
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_blender():
    hits = glob.glob(os.path.join(REPO, "tools", "blender", "**", "blender.exe"), recursive=True)
    if not hits:
        sys.exit("No se encontró blender.exe en tools/blender/.")
    return hits[0]


def run(cmd):
    print("›", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--scene", default=None)
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--frames", default="360")
    ap.add_argument("--res", default="360")
    ap.add_argument("--samples", default="32")
    ap.add_argument("--engine", default="eevee")
    ap.add_argument("--fps", default="24")
    ap.add_argument("--format", default="16:9")
    ap.add_argument("--math-overlay", action="store_true")
    ap.add_argument("--waveform", action="store_true")
    ap.add_argument("--attractor", type=str, default="chladni", choices=["lorenz", "rossler", "gravity", "thomas", "pendulum", "curl", "chladni", "reaction_diffusion"])
    ap.add_argument("--input-audio", type=str, required=True, help="Path to input audio file")
    a = ap.parse_args()

    outdir = os.path.join(REPO, "output", a.name)
    frames_dir = os.path.join(outdir, "frames")
    events = os.path.join(REPO, "data", f"{a.name}_events.json")
    os.makedirs(outdir, exist_ok=True)

    # 1) Render headless
    if not a.skip_render:
        if not a.scene:
            sys.exit("Falta --scene para renderizar (o usa --skip-render).")
        run([find_blender(), "--background", "--python", os.path.join(REPO, a.scene), "--",
             "--engine", a.engine, "--frames", a.frames, "--res", a.res,
             "--samples", a.samples, "--name", a.name, "--format", a.format])

    # 2) No audio generation needed, we use a.input_audio
    print(f"Using input audio: {a.input_audio}")

    # 3) Frames -> video silencioso
    video = os.path.join(outdir, "video_silent.mp4")
    run(["ffmpeg", "-y", "-framerate", a.fps, "-i", os.path.join(frames_dir, "%04d.png"),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", video])

    # 3.5) Math Overlay
    if a.math_overlay:
        overlay_dir = os.path.join(outdir, "overlay")
        res_h = int(a.res)
        res_w = int(res_h * 9 / 16) if a.format == "9:16" else int(res_h * 16 / 9)
        print("\n[clip] Generando overlay matemático...")
        run([sys.executable, os.path.join(REPO, "tools", "math_overlay.py"),
             "--frames", a.frames, "--outdir", overlay_dir, 
             "--res-w", str(res_w), "--res-h", str(res_h),
             "--fps", str(a.fps),
             "--attractor", a.attractor])
             
        video_math = os.path.join(outdir, "video_math.mp4")
        run(["ffmpeg", "-y", "-i", video, "-framerate", a.fps, "-i", os.path.join(overlay_dir, "%04d.png"),
             "-filter_complex", "[0:v][1:v]overlay=0:0[outv]", "-map", "[outv]", 
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", video_math])
        video = video_math

    # 4) (Removed Sidechain compression step)
    
    # 5) Video + audio -> clip final
    final = os.path.join(outdir, f"{a.name}.mp4")
    if a.waveform:
        res_w = int(int(a.res) * 9 / 16) if a.format == "9:16" else int(int(a.res) * 16 / 9)
        wave_flt = f"[1:a]showwaves=s={res_w}x120:mode=line:colors=orange,colorkey=black:0.1:0.1[wave];[0:v][wave]overlay=0:H-h[outv]"
        run(["ffmpeg", "-y", "-i", video, "-i", a.input_audio, "-filter_complex", wave_flt,
             "-map", "[outv]", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", 
             "-c:a", "aac", "-b:a", "192k", "-shortest", final])
    else:
        run(["ffmpeg", "-y", "-i", video, "-i", a.input_audio, "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-shortest", final])

    print(f"\n[clip] LISTO -> {final}")


if __name__ == "__main__":
    main()
