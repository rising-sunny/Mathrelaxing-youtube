"""
Short 9:16 Clifford Torus — 10s @ 60 fps + texto timed + música.

    python build_clifford_short.py
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_clifford"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "betawaves"
FRAMES = 600   # 10 s @ 60 fps
FPS = 60
RES = 1920     # altura → 1080×1920


def run(cmd):
    print("›", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    subprocess.run(cmd, check=True, cwd=REPO)


def main():
    music = find_track(MUSIC_TRACK)

    os.makedirs(OUTDIR, exist_ok=True)
    frames_dir = os.path.join(OUTDIR, "frames")
    overlay_dir = os.path.join(OUTDIR, "overlay")

    print(f"\n[{NAME}] === Short 10s Clifford Torus + texto ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080×1920")

    # 1) Render visual
    run([
        sys.executable,
        os.path.join(REPO, "scenes", "clifford_1h_numpy.py"),
        "--",
        "--engine", "numpy",
        "--frames", str(FRAMES),
        "--res", str(RES),
        "--name", NAME,
        "--format", "9:16",
    ])

    # 2) Texto timed
    run([
        sys.executable,
        os.path.join(REPO, "tools", "short_text_overlay.py"),
        "--outdir", overlay_dir,
        "--frames", str(FRAMES),
        "--fps", str(FPS),
        "--res-w", "1080",
        "--res-h", "1920",
    ])

    # 3) Video silencioso + overlay
    silent = os.path.join(OUTDIR, "video_silent.mp4")
    run([
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "%04d.png"),
        "-framerate", str(FPS),
        "-i", os.path.join(overlay_dir, "%04d.png"),
        "-filter_complex",
        "[0:v]scale=trunc(iw/2)*2:trunc(ih/2)*2[base];"
        "[base][1:v]overlay=0:0:format=auto[outv]",
        "-map", "[outv]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        silent,
    ])

    # 4) Audio 10s
    audio_cut = os.path.join(OUTDIR, "audio_cut.wav")
    dur = FRAMES / FPS
    run([
        "ffmpeg", "-y",
        "-i", music,
        "-t", str(dur),
        "-af", f"loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.4,afade=t=out:st={max(0, dur-0.8)}:d=0.8",
        "-ar", "48000", "-ac", "2",
        audio_cut,
    ])

    # 5) Mux final
    final = os.path.join(OUTDIR, f"{NAME}.mp4")
    run([
        "ffmpeg", "-y",
        "-i", silent,
        "-i", audio_cut,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        final,
    ])

    print(f"\n[{NAME}] LISTO -> {final}")
    print(f"[{NAME}] {dur:.0f}s | 9:16 | texto timed | {os.path.basename(music)}")


if __name__ == "__main__":
    main()
