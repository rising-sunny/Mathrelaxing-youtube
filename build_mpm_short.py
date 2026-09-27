"""
Short 9:16 — Cuatro materiales, una ecuacion: MPM con Taichi (15s).

Gelatina, nieve, arena y agua obedecen la misma conservacion del momento;
solo cambia la ley constitutiva.

Musica: partitura "shatter" de audio/orchestra.py (FluidSynth + MuseScore General).
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_mpm"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_SCORE = "shatter"
FRAMES = "900"
RES = "1920"
FPS = "60"



def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    lead = r"$\mathrm{4\ materials\ \cdot\ 1\ equation}$"
    law = (r"$\rho\,\frac{D\mathbf{v}}{Dt}=\nabla\cdot\boldsymbol{\sigma}"
           r"+\rho\,\mathbf{g}$")
    note = r"$\mathrm{same\ law,\ only\ the\ stress}\ \boldsymbol{\sigma}(F)\ \mathrm{changes}$"
    fps = ev["fps"]
    texts = []
    for f in range(frames):
        t = f / fps
        if t < ev["t_snow"]:
            txt = r"$\mathrm{JELLY:\ elastic,\ it\ springs\ back}$"
        elif t < ev["t_sand"]:
            txt = r"$\mathrm{SNOW:\ elastic\ until\ it\ CRACKS}$"
        elif t < ev["t_gate"]:
            txt = r"$\mathrm{SAND:\ pure\ friction,\ it\ piles\ up}$"
        elif t < 13.2:
            txt = r"$\mathrm{WATER:\ pressure\ only,\ it\ FLOWS}$"
        else:
            txt = (rf"$\mathrm{{{ev['n']:,}\ material\ points,\ one\ law}}$"
                   ).replace(",", "{,}")
        texts.append(txt)
    return {
        "scrim": {"rgb": [4, 5, 12],
                  "top": {"extent": 0.08, "strength": 0.75, "hold": 0.12},
                  "bottom": {"extent": 0.10, "strength": 0.55}},
        "static": [
            {"text": lead, "y": 0.946, "rgba": [1.0, 1.0, 1.0, 0.95], "size": 17},
            {"text": law,  "y": 0.900, "rgba": [1.0, 0.80, 0.45, 0.95], "size": 20},
            {"text": note, "y": 0.858, "rgba": [0.80, 0.88, 1.0, 0.88], "size": 15},
        ],
        "dynamic": {"y": 0.822, "rgba": [1.0, 0.82, 0.50, 0.96], "size": 17,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 cuatro materiales ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "mpm_materials.py"), "--",
            "--frames", FRAMES, "--res", RES, "--fps", FPS,
            "--name", NAME,
        ])
        if r.returncode != 0:
            sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "audio", "orchestra.py"),
        "--score", MUSIC_SCORE, "--outdir", OUTDIR,
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
        # loudnorm de una pasada va en modo dinamico y se pasa del techo:
        # con este preset dejaba el pico real en +0.9 dBFS, o sea recortando.
        # El limitador detras es la red de seguridad (0.84 = -1.5 dBFS).
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.84:level=false",
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
        "-i", with_math, "-o", branded, "--cta-y", "0.885", "--handle-y", "0.028",
    ])
    if r.returncode != 0:
        sys.exit("Error quemando el CTA.")

    print(f"\n[{NAME}] LISTO -> {branded}")


if __name__ == "__main__":
    main()
