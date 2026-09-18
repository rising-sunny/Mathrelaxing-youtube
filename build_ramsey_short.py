"""
Short 9:16 — R(3,3) = 6 (15s @ 60 fps).

Con cinco nodos se puede pintar el grafo completo sin dejar ningun triangulo
monocromatico. Con seis es imposible, y no por poco: el minimo sobre los 32768
coloreos de K6 es DOS. Todo enumerado en la escena, no citado.

Musica: preset "drift" de audio/ambient_score.py — Re dorico, que no resuelve.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_ramsey"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "drift"
FRAMES = "900"
RES = "1920"
FPS = "60"

RULE = r"$\mathrm{colour\ every\ edge\ red\ or\ blue}$"


def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    k5 = (rf"$K_5:\ 2^{{10}}={ev['k5_total']:,}".replace(",", r"\,")
          + rf"\ \mathrm{{colourings}}\ \cdot\ {ev['k5_free']}"
          rf"\ \mathrm{{with\ no\ mono\ triangle}}$")
    k6 = (rf"$K_6:\ 2^{{15}}={ev['k6_total']:,}".replace(",", r"\,")
          + rf"\ \mathrm{{colourings}}\ \cdot\ {ev['k6_free']}"
          rf"\ \mathrm{{with\ none}}$")
    fg = ev["f_grow"]
    texts = [(r"$R(3,3)=\ ?$" if f < fg
              else rf"$R(3,3)=6\ \ \cdot\ \ \mathrm{{fewest\ possible:}}"
                   rf"\ {ev['k6_min']}$") for f in range(frames)]
    return {
        "scrim": {"rgb": [4, 6, 16],
                  "top": {"extent": 0.24, "strength": 0.94},
                  "bottom": {"extent": 0.14, "strength": 0.58}},
        "static": [
            {"text": RULE, "y": 0.946, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 21},
            {"text": k5,   "y": 0.910, "rgba": [0.45, 0.92, 1.0, 0.90], "size": 15},
            {"text": k6,   "y": 0.878, "rgba": [1.0, 0.58, 0.42, 0.94], "size": 15},
        ],
        "dynamic": {"y": 0.842, "rgba": [1.0, 0.82, 0.36, 0.96], "size": 20,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 R(3,3) = 6 ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "ramsey.py"), "--",
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
    print(f"[{NAME}] Subir con: python upload_ramsey_short.py")


if __name__ == "__main__":
    main()
