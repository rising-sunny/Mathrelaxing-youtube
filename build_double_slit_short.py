"""
Short 9:16 — Doble rendija, un electron a la vez (15s).

La onda de un electron (Schrodinger, split-step) cruza las dos rendijas,
colapsa en un punto de la placa; despues una lluvia de electrones levanta
las franjas, y al encender un detector en las rendijas desaparecen.

Musica: preset "titan" de audio/ambient_score.py.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_slit"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "titan"
FRAMES = "900"
RES = "1920"
FPS = "60"



def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    lead = r"$\mathrm{Double\ Slit\ \cdot\ one\ electron\ at\ a\ time}$"
    law = (r"$i\hbar\,\frac{\partial\psi}{\partial t}=-\frac{\hbar^2}{2m}"
           r"\nabla^2\psi+V\psi$")
    note = r"$\mathrm{colour=phase\ of}\ \psi\ \ \cdot\ \ \mathrm{brightness}=|\psi|$"
    fps = ev["fps"]
    texts = []
    for f in range(frames):
        t = f / fps
        sh = ev["shown"][min(f, len(ev["shown"]) - 1)]
        n2, n3 = sh["n2"], sh["n3"]
        if t < ev["t1"]:
            txt = r"$\mathrm{one\ electron:\ its\ wave\ goes\ through\ BOTH\ slits}$"
        elif t < ev["t1"] + 0.9:
            txt = r"$\mathrm{detected:\ ONE\ dot.\ The\ wave\ is\ gone}$"
        elif t < ev["t_drop"]:
            txt = (rf"$\mathrm{{each\ wave\ is\ one\ electron\ \cdot\ detected}}\ {n2:,}$"
                   ).replace(",", "{,}")
        elif t < ev["t_twist"] + 0.6:
            txt = r"$\mathrm{now\ WATCH\ which\ slit\ it\ takes...}$"
        elif t < 14.2:
            txt = (rf"$\mathrm{{detector\ ON\ \cdot\ detected}}\ {n3:,}$").replace(",", "{,}")
        else:
            txt = r"$\mathrm{watched:\ the\ fringes\ are\ GONE}$"
        texts.append(txt)
    return {
        "scrim": {"rgb": [3, 4, 10],
                  "top": {"extent": 0.05, "strength": 0.85, "hold": 0.15},
                  "bottom": {"extent": 0.13, "strength": 0.70}},
        "static": [
            {"text": lead, "y": 0.946, "rgba": [1.0, 1.0, 1.0, 0.95], "size": 17},
            {"text": law,  "y": 0.900, "rgba": [1.0, 0.80, 0.34, 0.95], "size": 20},
            {"text": note, "y": 0.858, "rgba": [0.70, 0.84, 1.0, 0.88], "size": 15},
        ],
        "dynamic": {"y": 0.822, "rgba": [1.0, 0.84, 0.42, 0.96], "size": 17,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 doble rendija ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "double_slit.py"), "--",
            "--frames", FRAMES, "--res", RES, "--fps", FPS,
            "--name", NAME,
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
