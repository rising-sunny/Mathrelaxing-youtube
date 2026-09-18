"""
Short 9:16 — Teorema de las tres distancias (15s @ 60 fps).

Cascada que se comprime: la fila N son los N puntos {k*alpha} sobre el
intervalo, con cada hueco pintado segun a cual de las tres longitudes
pertenece. Se ven siempre todas las filas desde N=1, asi que la imagen no
repite nada: empieza en tres franjas y termina en un tejido de 520 filas.

Musica: preset "bloom" de audio/ambient_score.py — Mi bemol mayor, I-vi-IV-V.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_three"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "bloom"
FRAMES = "900"
RES = "1920"
FPS = "60"

SETUP = (r"$\{\alpha\},\{2\alpha\},\ldots,\{N\alpha\}"
         r"\ \ \mathrm{on\ a\ circle\ of\ length}\ 1$")
CLAIM = r"$\mathrm{the\ gaps\ take\ at\ most\ THREE\ distinct\ lengths}$"
SUM = r"$\mathrm{and\ when\ there\ are\ three,}\ \ \ell_{3}=\ell_{1}+\ell_{2}$"


def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    shown, lengths = ev["shown"], ev["lengths"]
    texts = []
    for f in range(frames):
        n = shown[min(f, len(shown) - 1)]
        k = lengths[n - 1]
        texts.append(rf"$N={n}\ \ \cdot\ \ \mathrm{{distinct\ gap\ lengths:}}\ {k}$")
    return {
        "scrim": {"rgb": [5, 6, 16],
                  "top": {"extent": 0.24, "strength": 0.94},
                  "bottom": {"extent": 0.14, "strength": 0.60}},
        "static": [
            {"text": SETUP, "y": 0.944, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 19},
            {"text": CLAIM, "y": 0.906, "rgba": [1.0, 0.82, 0.34, 0.94], "size": 18},
            {"text": SUM,   "y": 0.871, "rgba": [0.45, 0.92, 1.0, 0.86], "size": 17},
        ],
        "dynamic": {"y": 0.836, "rgba": [1.0, 0.80, 0.36, 0.95], "size": 19,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 tres distancias ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "three_distance.py"), "--",
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
        "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
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
        "-c:v", "libx264", "-crf", "17", "-preset", "medium",
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
    print(f"[{NAME}] Subir con: python upload_three_short.py")


if __name__ == "__main__":
    main()
