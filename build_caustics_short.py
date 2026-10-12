"""
Short 9:16 — Causticas: la luz del sol en el fondo de una piscina (15s).

Ecuacion de ondas en la superficie, Snell exacto para cada rayo; brisa,
lluvia, una piedra y viento.

Musica: partitura "shimmer" de audio/orchestra.py; cada gota es una nota.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_caustics"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_SCORE = "shimmer"
FRAMES = "900"
RES = "1920"
FPS = "60"



def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    lead = r"$\mathrm{Caustics\ \cdot\ sunlight\ in\ a\ pool}$"
    law = r"$n_1\sin\theta_1=n_2\sin\theta_2$"
    note = r"$\mathrm{a\ wave\ focuses\ light\ at\ depth}\ D=\frac{1}{(1-1/n)\,A\,k^2}$"
    fps = ev["fps"]
    w0, w1 = ev["t_wind"]
    texts = []
    for f in range(frames):
        t = f / fps
        if t < ev["t_rain"]:
            txt = r"$\mathrm{every\ bright\ line\ is\ light\ focused\ by\ a\ wave}$"
        elif t < ev["t_stone"]:
            txt = r"$\mathrm{rain:\ every\ ripple\ is\ a\ moving\ lens}$"
        elif t < w0:
            txt = r"$\mathrm{a\ stone:\ one\ big\ lens}$"
        elif t < w1:
            txt = r"$\mathrm{wind:\ the\ web\ you\ see\ in\ every\ pool}$"
        else:
            txt = r"$\mathrm{calm\ again}$"
        texts.append(txt)
    return {
        "scrim": {"rgb": [4, 18, 30],
                  "top": {"extent": 0.06, "strength": 0.72, "hold": 0.20},
                  "bottom": {"extent": 0.10, "strength": 0.50}},
        "static": [
            {"text": lead, "y": 0.946, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 17},
            {"text": law,  "y": 0.900, "rgba": [1.0, 0.85, 0.50, 0.96], "size": 20},
            {"text": note, "y": 0.852, "rgba": [0.85, 0.95, 1.0, 0.92], "size": 15},
        ],
        "dynamic": {"y": 0.812, "rgba": [1.0, 0.86, 0.55, 0.97], "size": 16,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 causticas ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "caustics.py"), "--",
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
