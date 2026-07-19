"""
build_music_short.py — Short 9:16 sin Blender, visual reactivo + pista externa.

    python build_music_short.py \
        --audio "C:/path/to/track.wav" \
        --duration 30 --start 0

Produce: output/shorts_spectral/shorts_spectral.mp4
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print("›", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    subprocess.run(cmd, check=True, cwd=REPO)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--audio",
        default=r"C:\Users\sunse\Downloads\ES_How Did We Get Here - Hanna Lindgren.wav",
    )
    ap.add_argument("--name", default="shorts_spectral")
    ap.add_argument("--start", type=float, default=0.0, help="Segundo de inicio del recorte")
    ap.add_argument("--duration", type=float, default=30.0, help="Duración del short (s)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--grid", type=int, default=288)
    ap.add_argument("--width", type=int, default=576)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--waveform", action="store_true", help="Overlay de waveform naranja")
    ap.add_argument("--math-overlay", action="store_true", default=True,
                    help="Ecuaciones LaTeX (Computer Modern) sobre el video")
    ap.add_argument("--no-math-overlay", action="store_true",
                    help="Desactiva el overlay matemático")
    a = ap.parse_args()
    use_math = a.math_overlay and not a.no_math_overlay

    if not os.path.isfile(a.audio):
        sys.exit(f"No se encontró el audio: {a.audio}")

    outdir = os.path.join(REPO, "output", a.name)
    frames_dir = os.path.join(outdir, "frames")
    os.makedirs(outdir, exist_ok=True)

    # 1) Render numpy
    if not a.skip_render:
        run([
            sys.executable,
            os.path.join(REPO, "scenes", "spectral_cymatics.py"),
            "--audio", a.audio,
            "--name", a.name,
            "--start", str(a.start),
            "--duration", str(a.duration),
            "--fps", str(a.fps),
            "--grid", str(a.grid),
            "--width", str(a.width),
            "--height", str(a.height),
        ])

    # Contar frames reales
    n_frames = len([f for f in os.listdir(frames_dir) if f.endswith(".png")])
    if n_frames == 0:
        sys.exit("No hay frames en " + frames_dir)
    print(f"[build] {n_frames} frames @ {a.fps} fps")

    # 2) Frames → video silencioso (dims pares)
    silent = os.path.join(outdir, "video_silent.mp4")
    run([
        "ffmpeg", "-y",
        "-framerate", str(a.fps),
        "-i", os.path.join(frames_dir, "%04d.png"),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        silent,
    ])
    video = silent

    # 2.5) Overlay matemático (LaTeX / Computer Modern)
    if use_math:
        events = os.path.join(REPO, "data", f"{a.name}_events.json")
        overlay_dir = os.path.join(outdir, "overlay")
        res_w = max(2, (a.width // 2) * 2)
        res_h = max(2, (a.height // 2) * 2)
        run([
            sys.executable,
            os.path.join(REPO, "tools", "spectral_math_overlay.py"),
            "--events", events,
            "--outdir", overlay_dir,
            "--res-w", str(res_w),
            "--res-h", str(res_h),
            "--fps", str(a.fps),
        ])
        video_math = os.path.join(outdir, "video_math.mp4")
        run([
            "ffmpeg", "-y",
            "-i", video,
            "-framerate", str(a.fps),
            "-i", os.path.join(overlay_dir, "%04d.png"),
            "-filter_complex", "[0:v][1:v]overlay=0:0[outv]",
            "-map", "[outv]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
            video_math,
        ])
        video = video_math

    # 3) Recorte de audio (misma ventana)
    audio_cut = os.path.join(outdir, "audio_cut.wav")
    run([
        "ffmpeg", "-y",
        "-ss", str(a.start),
        "-i", a.audio,
        "-t", str(a.duration),
        "-af", "afade=t=in:st=0:d=0.8,afade=t=out:st={}:d=1.2".format(max(0.0, a.duration - 1.2)),
        "-ar", "48000", "-ac", "2",
        audio_cut,
    ])

    # 4) Mux final
    final = os.path.join(outdir, f"{a.name}.mp4")
    if a.waveform:
        res_w = max(2, (a.width // 2) * 2)
        wave_flt = (
            f"[1:a]showwaves=s={res_w}x100:mode=line:colors=0xFFAA44,colorkey=black:0.1:0.1[wave];"
            f"[0:v][wave]overlay=0:H-h[outv]"
        )
        run([
            "ffmpeg", "-y",
            "-i", video, "-i", audio_cut,
            "-filter_complex", wave_flt,
            "-map", "[outv]", "-map", "1:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", final,
        ])
    else:
        run([
            "ffmpeg", "-y",
            "-i", video, "-i", audio_cut,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", final,
        ])

    print(f"\n[build] LISTO → {final}")
    print(f"        {n_frames} frames | {a.duration}s | 9:16 | math={use_math} | música: {os.path.basename(a.audio)}")


if __name__ == "__main__":
    main()
