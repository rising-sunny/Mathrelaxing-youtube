"""
Short 9:16 — Pulsar: plegar rotaciones para sacar la senal del ruido (15s).

Cada fila de la pila es una rotacion de PSR B1919+21. Los pulsos sueltos
varian; el promedio no. La pila crece de una fila a ochenta, que es la imagen
de la portada de "Unknown Pleasures".

Musica: preset "beacon" de audio/ambient_score.py — Si menor, con la melodia
reducida a un blip cada dos tiempos. Un pulsar es un reloj.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_pulsar"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "beacon"
FRAMES = "900"
RES = "1920"
FPS = "60"


def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    lead = (rf"$\mathrm{{PSR\ B1919+21}}\ \cdot\ P={ev['period_s']}\ \mathrm{{s}}"
            rf"\ \cdot\ \mathrm{{simulated}}$")
    law = r"$\mathrm{stack\ }N\mathrm{\ rotations:}\ \ \mathrm{S/N}\propto\sqrt{N}$"
    fit = (rf"$\mathrm{{measured\ exponent}}\ {ev['exponent']:.3f}"
           rf"\ \ (R^2={ev['fit_r2']:.4f})$")
    texts = []
    for f in range(frames):
        i = min(f, len(ev["n_shown"]) - 1)
        texts.append(rf"$\mathrm{{rotation}}\ {ev['n_shown'][i]}\,/\,{ev['rows']}"
                     rf"\ \ \cdot\ \ \mathrm{{peak/noise}}\ "
                     rf"{ev['snr_shown'][i]:.1f}$")
    return {
        "scrim": {"rgb": [4, 6, 16],
                  "top": {"extent": 0.25, "strength": 0.95},
                  "bottom": {"extent": 0.13, "strength": 0.58}},
        "static": [
            {"text": lead, "y": 0.944, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 18},
            {"text": law,  "y": 0.908, "rgba": [1.0, 0.82, 0.34, 0.94], "size": 19},
            {"text": fit,  "y": 0.874, "rgba": [0.45, 0.92, 1.0, 0.86], "size": 16},
        ],
        "dynamic": {"y": 0.838, "rgba": [1.0, 0.84, 0.42, 0.96], "size": 19,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 pulsar ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "pulsar.py"), "--",
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
    print(f"[{NAME}] Subir con: python upload_pulsar_short.py")


if __name__ == "__main__":
    main()
