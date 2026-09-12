"""
Short 9:16 — Plegado parametrico propio (15s @ 60 fps).

Una hoja de puntos doblada por una cadena de expresiones, sin simulacion.
LOOP EXACTO: todos los terminos temporales son 2*pi por un entero, asi que el
ultimo frame empalma con el primero (verificado: |fold(1)-fold(0)| = 1e-13).

Musica: preset "drift" de audio/ambient_score.py — Re dorico, i-IV-i-bVII.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_fold"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_PRESET = "drift"
FRAMES = "900"
RES = "1920"
FPS = "60"

SEED = r"$a=7.2\,y\qquad s=\sin(50x)\,\cos(6.8y)$"
RAD = r"$r=20+46y+15\sin(2.6a-6\pi\tau)+12s$"
ANG = r"$c=a+0.55\sin(1.4a-2\pi\tau)+0.3s-2\pi\tau$"


def overlay_spec():
    frames = int(FRAMES)
    texts = [rf"$(u,v)=\left(r\sin c,\ (r+10s)\cos c\right)"
             rf"\quad \tau={f / frames:.3f}$" for f in range(frames)]
    return {
        "scrim": {"rgb": [6, 7, 18],
                  "top": {"extent": 0.27, "strength": 0.92},
                  "bottom": {"extent": 0.12, "strength": 0.52}},
        "static": [
            {"text": SEED, "y": 0.932, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 20},
            {"text": RAD,  "y": 0.894, "rgba": [1.0, 0.82, 0.34, 0.93], "size": 18},
            {"text": ANG,  "y": 0.858, "rgba": [0.45, 0.92, 1.0, 0.86], "size": 18},
        ],
        "dynamic": {"y": 0.818, "rgba": [1.0, 0.80, 0.36, 0.95], "size": 18,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 plegado parametrico ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "parametric_fold.py"), "--",
            "--frames", FRAMES, "--res", RES, "--fps", FPS,
            "--name", NAME, "--format", "9:16",
        ])
        if r.returncode != 0:
            sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "audio", "ambient_score.py"),
        "--preset", MUSIC_PRESET, "--outdir", OUTDIR,
        "--duration", str(int(FRAMES) / int(FPS)),
    ])
    if r.returncode != 0:
        sys.exit("Error componiendo la musica.")

    clip = os.path.join(OUTDIR, f"{NAME}.mp4")
    r = subprocess.run([
        "ffmpeg", "-y", "-framerate", FPS,
        "-i", os.path.join(OUTDIR, "frames", "%04d.png"),
        "-i", os.path.join(OUTDIR, "music.wav"),
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k", "-shortest", clip,
    ])
    if r.returncode != 0:
        sys.exit("Error en el ensamblaje del clip.")

    overlay_dir = os.path.join(OUTDIR, "overlay")
    spec_path = os.path.join(OUTDIR, "overlay_spec.json")
    with open(spec_path, "w", encoding="utf-8") as fh:
        json.dump(overlay_spec(), fh)
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "tools", "latex_overlay.py"),
        "--spec", spec_path, "--outdir", overlay_dir,
        "--res-w", "1080", "--res-h", "1920",
    ])
    if r.returncode != 0:
        sys.exit("Error generando el overlay matematico.")

    with_math = os.path.join(OUTDIR, f"{NAME}_math.mp4")
    r = subprocess.run([
        "ffmpeg", "-y", "-i", clip, "-framerate", FPS,
        "-i", os.path.join(overlay_dir, "%04d.png"),
        "-filter_complex", "[0:v][1:v]overlay=0:0[v]", "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-pix_fmt", "yuv420p", "-c:a", "copy", with_math,
    ])
    if r.returncode != 0:
        sys.exit("Error componiendo el overlay.")

    branded = os.path.join(OUTDIR, f"{NAME}_branded.mp4")
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "tools", "brand_cta.py"),
        "-i", with_math, "-o", branded, "--cta-y", "0.795", "--handle-y", "0.028",
    ])
    if r.returncode != 0:
        sys.exit("Error quemando el CTA.")

    print(f"\n[{NAME}] LISTO -> {branded}")
    print(f"[{NAME}] Subir con: python upload_fold_short.py")


if __name__ == "__main__":
    main()
