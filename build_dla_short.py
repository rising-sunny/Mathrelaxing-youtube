"""
Short 9:16 — Agregacion limitada por difusion (15s @ 60 fps).

Un caminante al azar por vez, una regla de contacto, y sale una estructura
ramificada cuya dimension fractal nadie sabe derivar. La escena la mide sobre
el cumulo que acaba de generar y el numero que se muestra es ese, no uno de
manual. NO es un loop: crece de una semilla al cumulo entero.

Musica: preset "bloom" de audio/ambient_score.py — Mi bemol mayor, I-vi-IV-V,
con motivo melodico escrito. En mayor porque aca la pieza acompana algo que
crece.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_dla"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "bloom"
FRAMES = "900"
RES = "1920"
FPS = "60"

LAW = r"$N(r)\propto r^{D}$"
ACCEPTED = r"$\mathrm{accepted\ value:}\ D\simeq 1.71,\ \mathrm{no\ derivation\ known}$"


def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    total, reveal = ev["n_particles"], ev["reveal_frames"]
    measured = (rf"$\mathrm{{this\ cluster:}}\ D={ev['dimension']:.2f}$"
                rf"$\ \ (R^2={ev['fit_r2']:.4f})$")

    texts = []
    for f in range(frames):
        n = max(12, int(total * min(1.0, (f + 1) / reveal)))
        digits = f"{n:,}".replace(",", r"\,")
        texts.append(rf"${digits}\ \mathrm{{random\ walkers\ stuck}}$")
    return {
        "scrim": {"rgb": [7, 9, 22],
                  "top": {"extent": 0.27, "strength": 0.91},
                  "bottom": {"extent": 0.12, "strength": 0.52}},
        "static": [
            {"text": LAW,      "y": 0.930, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 26},
            {"text": measured, "y": 0.879, "rgba": [1.0, 0.82, 0.34, 0.93], "size": 18},
            {"text": ACCEPTED, "y": 0.844, "rgba": [0.45, 0.92, 1.0, 0.84], "size": 16},
        ],
        "dynamic": {"y": 0.806, "rgba": [1.0, 0.80, 0.36, 0.95], "size": 21,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 agregacion limitada por difusion ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "dla.py"), "--",
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
    print(f"[{NAME}] Subir con: python upload_dla_short.py")


if __name__ == "__main__":
    main()
