"""
Short 9:16 — Navier-Stokes 2-D: por que el caso plano esta resuelto (15s).

La vorticidad en 2-D es un escalar transportado y difundido, asi que obedece
el principio del maximo y no puede explotar. En 3-D es un vector, aparece el
estiramiento de vortices, y el problema sigue abierto y vale un millon.

Musica: preset "cascade" de audio/ambient_score.py — Mi menor, melodia que
cae en tres frases y solo al final remonta.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_navier_stokes"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "cascade"
FRAMES = "900"
RES = "1920"
FPS = "60"
NU = "3.0e-5"
TURNS = "45"


def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    lead = (rf"$\mathrm{{2D\ Navier\!-\!Stokes}}\ \cdot\ "
            rf"{ev['nx']}\times{ev['ny']}\ \mathrm{{pseudospectral}}$")
    law = (r"$\partial_t\omega+\mathbf{u}\!\cdot\!\nabla\omega"
           r"=\nu\,\nabla^2\omega$")
    note = (r"$\omega\ \mathrm{is\ a\ scalar\ in\ 2D:}\ "
            r"\max|\omega|\ \mathrm{can\ only\ fall}$")
    texts = []
    for f in range(frames):
        i = min(f, len(ev["wmax"]) - 1)
        texts.append(rf"$\max|\omega|\ {ev['wmax'][i]:.2f}\ \ \cdot\ \ "
                     rf"\mathrm{{vortices}}\ {ev['vortices'][i]}\ \ \cdot\ \ "
                     rf"\mathrm{{enstrophy}}\ {ev['enstrophy_frac'][i]*100:.0f}\%$")
    return {
        "scrim": {"rgb": [3, 5, 14],
                  "top": {"extent": 0.27, "strength": 0.96},
                  "bottom": {"extent": 0.16, "strength": 0.72}},
        "static": [
            {"text": lead, "y": 0.946, "rgba": [1.0, 1.0, 1.0, 0.95], "size": 17},
            {"text": law,  "y": 0.906, "rgba": [1.0, 0.80, 0.34, 0.95], "size": 21},
            {"text": note, "y": 0.868, "rgba": [0.42, 0.90, 1.0, 0.88], "size": 15},
        ],
        "dynamic": {"y": 0.828, "rgba": [1.0, 0.84, 0.42, 0.96], "size": 17,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 Navier-Stokes 2-D ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "navier_stokes.py"), "--",
            "--frames", FRAMES, "--res", RES, "--fps", FPS,
            "--nu", NU, "--turns", TURNS, "--name", NAME,
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
        "-i", with_math, "-o", branded, "--cta-y", "0.885", "--handle-y", "0.028",
    ])
    if r.returncode != 0:
        sys.exit("Error quemando el CTA.")

    print(f"\n[{NAME}] LISTO -> {branded}")


if __name__ == "__main__":
    main()
