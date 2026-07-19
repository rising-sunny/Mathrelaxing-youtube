import subprocess
import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
NAME = "abc_loop_preview"
FRAMES = 1200
FPS = 60
RES = "720"
SAMPLES = "16"
FORMAT = "16:9"

def run(cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=REPO, check=True)

def main():
    outdir = os.path.join(REPO, "output", NAME)
    frames_dir = os.path.join(outdir, "frames")
    os.makedirs(outdir, exist_ok=True)
    
    # 1. Render base frames (fast settings for preview)
    cmd = [
        sys.executable, os.path.join("render", "build_clip.py"),
        "--name", NAME,
        "--scene", "scenes/abc_flow_1h.py",
        "--attractor", "abc",
        "--engine", "eevee",
        "--frames", str(FRAMES),
        "--res", RES,
        "--samples", SAMPLES,
        "--fps", str(FPS),
        "--format", FORMAT
    ]
    MAX = 10
    for attempt in range(1, MAX + 1):
        print(f"\n=== Render Intento {attempt}/{MAX} ===")
        r = subprocess.run(cmd, cwd=REPO)
        if r.returncode == 0:
            break
        print(f"Crash detectado, reintentando...")
        import time
        time.sleep(2)

    
    video_in = os.path.join(outdir, "video_silent.mp4")
    video_seamless = os.path.join(outdir, "seamless_preview.mp4")
    
    # 2. Split, swap and crossfade
    print("\n[preview] Creando loop sin costuras con FFmpeg...")
    filter_complex = (
        "[0:v]split[v1][v2]; "
        "[v1]trim=start=0:end=10,setpts=PTS-STARTPTS[p1]; "
        "[v2]trim=start=10:end=20,setpts=PTS-STARTPTS[p2]; "
        "[p2][p1]xfade=transition=fade:duration=2:offset=8[out]"
    )
    
    run([
        "ffmpeg", "-y", "-i", video_in,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23",
        video_seamless
    ])
    
    print(f"\n[preview] LISTO! Vista previa generada en {video_seamless}")

if __name__ == "__main__":
    main()
