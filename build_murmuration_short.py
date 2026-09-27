"""
Short 9:16 — Murmuracion: 30000 estorninos, cada uno siguiendo a 7 vecinos (15s).

Del caos al orden, el ataque de un halcon y la bajada a los juncos al
anochecer.

Musica: preset "murmur" de audio/ambient_score.py.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_murmur"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "murmur"
FRAMES = "900"
RES = "1920"
FPS = "60"



def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    lead = (rf"$\mathrm{{Murmuration\ \cdot\ {ev['n']:,}\ starlings}}$").replace(",", "{,}")
    law = (r"$\mathbf{v}_i\ \longleftarrow\ \langle\,\mathbf{v}_j\,\rangle"
           r"_{\mathrm{7\ nearest}}$")
    note = r"$\varphi=|\langle\hat{\mathbf{v}}\rangle|:\ \ 0\ \mathrm{chaos},\ \ 1\ \mathrm{perfect\ order}$"
    fps = ev["fps"]
    texts = []
    for f in range(frames):
        t = f / fps
        sh = ev["shown"][min(f, len(ev["shown"]) - 1)]
        phi, n = sh["phi"], sh["n"]
        if t < ev["t_order"] + 0.8:
            txt = rf"$\mathrm{{no\ leader,\ no\ plan}}\ \cdot\ \varphi={phi:.2f}$"
        elif t < ev["t_falcon"][0] - 0.2:
            txt = rf"$\mathrm{{order\ from\ 7\ neighbours}}\ \cdot\ \varphi={phi:.2f}$"
        elif t < ev["t_roost"]:
            txt = rf"$\mathrm{{FALCON!\ panic\ spreads}}\ \cdot\ \varphi={phi:.2f}$"
        else:
            txt = (rf"$\mathrm{{into\ the\ reeds:}}\ {n:,}\ \mathrm{{still\ flying}}$"
                   ).replace(",", "{,}")
        texts.append(txt)
    return {
        "scrim": {"rgb": [6, 6, 16],
                  "top": {"extent": 0.10, "strength": 0.70, "hold": 0.10},
                  "bottom": {"extent": 0.13, "strength": 0.60}},
        "static": [
            {"text": lead, "y": 0.946, "rgba": [1.0, 1.0, 1.0, 0.95], "size": 17},
            {"text": law,  "y": 0.900, "rgba": [1.0, 0.80, 0.45, 0.95], "size": 20},
            {"text": note, "y": 0.858, "rgba": [0.85, 0.85, 1.0, 0.88], "size": 15},
        ],
        "dynamic": {"y": 0.822, "rgba": [1.0, 0.82, 0.50, 0.96], "size": 17,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 murmuracion ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "murmuration.py"), "--",
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
