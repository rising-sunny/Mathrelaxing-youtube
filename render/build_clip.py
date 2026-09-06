"""
build_clip.py — Orquestador genérico de clips MathRelaxing.

Cadena: render headless (Blender) -> audio (drone + hits) -> mux con ducking (FFmpeg).
Produce output/<name>/<name>.mp4

    python render/build_clip.py --name flow --scene scenes/flow_field.py \
        --engine eevee --frames 360 --res 360 --samples 32
    python render/build_clip.py --name flow --skip-render     # reusa frames + eventos
"""

import argparse
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from paths import find_blender  # noqa: E402


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
    ap.add_argument("--attractor", type=str, default="lorenz", choices=["lorenz", "rossler", "gravity", "thomas", "pendulum", "curl", "chladni", "reaction_diffusion", "chladni_melody", "abc", "tokamak", "aizawa", "hopf", "threebody", "clifford"])
    ap.add_argument("--music", type=str, default=None, help="Ruta a una pista musical externa (mp3/wav) para usar como fondo en vez del drone sintetizado, con los golpes de la simulacion 'ducking' por encima")
    a = ap.parse_args()

    outdir = os.path.join(REPO, "output", a.name)
    frames_dir = os.path.join(outdir, "frames")
    events = os.path.join(REPO, "data", f"{a.name}_events.json")
    os.makedirs(outdir, exist_ok=True)

    # 1) Render headless
    if not a.skip_render:
        if not a.scene:
            sys.exit("Falta --scene para renderizar (o usa --skip-render).")
        
        if a.engine == "numpy":
            run([sys.executable, os.path.join(REPO, a.scene), "--",
                 "--engine", a.engine, "--frames", a.frames, "--res", a.res,
                 "--samples", a.samples, "--name", a.name, "--format", a.format])
        else:
            run([find_blender(), "--background", "--python", os.path.join(REPO, a.scene), "--",
                 "--engine", a.engine, "--frames", a.frames, "--res", a.res,
                 "--samples", a.samples, "--name", a.name, "--format", a.format])

    # 2) Audio: drone + hits desde los eventos
    run([sys.executable, os.path.join(REPO, "audio", "build_audio.py"),
         "--events", events, "--outdir", outdir, "--attractor", a.attractor])

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
             "--attractor", a.attractor, "--name", a.name])
             
        video_math = os.path.join(outdir, "video_math.mp4")
        run(["ffmpeg", "-y", "-i", video, "-framerate", a.fps, "-i", os.path.join(overlay_dir, "%04d.png"),
             "-filter_complex", "[0:v][1:v]overlay=0:0[outv]", "-map", "[outv]", 
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", video_math])
        video = video_math

    # 4) Fondo (drone sintetizado o pista musical externa) "ducked" por los hits + mezcla
    amix = os.path.join(outdir, "audio_mix.wav")
    duration_s = float(a.frames) / float(a.fps)

    if a.music:
        bed = os.path.join(outdir, "music_trimmed.wav")
        fade_start = max(0.0, duration_s - 0.8)
        # loudnorm lleva la pista a un nivel de referencia parejo, sin depender
        # del masterizado original del mp3 (que suele venir mas bajo que nuestros wav)
        run(["ffmpeg", "-y", "-i", a.music, "-t", str(duration_s),
             "-af", f"loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.6,afade=t=out:st={fade_start}:d=0.8",
             bed])
    else:
        bed = os.path.join(outdir, "drone.wav")

    if a.attractor == "chladni_melody" and not a.music:
        # Keep the drone (cinematic pad) very loud without ducking it
        flt = "[0:a][1:a]amix=inputs=2:duration=longest:weights=2.0 1.0:normalize=0[mix];[mix]alimiter=limit=0.95[mixout]"
    elif a.music:
        # Ducking mas suave (la musica es el fondo principal) + sin normalizar
        # para que amix no aplaste el volumen automaticamente; limitador al final
        # como red de seguridad contra clipping.
        flt = ("[0:a][1:a]sidechaincompress=threshold=0.08:ratio=4:attack=20:release=350[duck];"
               "[duck][1:a]amix=inputs=2:duration=longest:weights=2.4 1.3:normalize=0[mix];"
               "[mix]alimiter=limit=0.95[mixout]")
    else:
        flt = ("[0:a][1:a]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[duck];"
               "[duck][1:a]amix=inputs=2:duration=longest:weights=1 1.3:normalize=0[mix];"
               "[mix]alimiter=limit=0.95[mixout]")
    run(["ffmpeg", "-y", "-i", bed, "-i", os.path.join(outdir, "hits.wav"),
         "-filter_complex", flt, "-map", "[mixout]", amix])

    # 5) Video + audio -> clip final
    final = os.path.join(outdir, f"{a.name}.mp4")
    if a.waveform:
        res_w = int(int(a.res) * 9 / 16) if a.format == "9:16" else int(int(a.res) * 16 / 9)
        wave_flt = f"[1:a]showwaves=s={res_w}x120:mode=line:colors=orange,colorkey=black:0.1:0.1[wave];[0:v][wave]overlay=0:H-h[outv]"
        run(["ffmpeg", "-y", "-i", video, "-i", amix, "-filter_complex", wave_flt,
             "-map", "[outv]", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", 
             "-c:a", "aac", "-b:a", "192k", "-shortest", final])
    else:
        run(["ffmpeg", "-y", "-i", video, "-i", amix, "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-shortest", final])

    print(f"\n[clip] LISTO -> {final}")


if __name__ == "__main__":
    main()
