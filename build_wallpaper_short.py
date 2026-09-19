"""
Short 9:16 — Los 17 grupos de papel tapiz (15s @ 60 fps).

Recorre los 17 ordenados por simetria creciente, de p1 (solo traslaciones) a
p6m (12 simetrias puntuales), con el ultimo sostenido como remate. El patron
se desplaza continuamente, que en una funcion periodica es gratis y exacto.

Musica: preset "lattice" de audio/ambient_score.py — La menor con ostinato.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_wallpaper"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "lattice"
FRAMES = "900"
RES = "1920"
FPS = "60"

LEAD = r"$\mathrm{every\ repeating\ pattern\ in\ the\ plane}$"
CLAIM = r"$\mathrm{falls\ into\ one\ of\ exactly\ }17\mathrm{\ symmetry\ groups}$"
WHO = r"$\mathrm{Fedorov,\ 1891\ \cdot\ not\ 16,\ not\ 18}$"


def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    groups, shown, total = ev["groups"], ev["shown"], ev["total"]
    texts = []
    for f in range(frames):
        g = groups[shown[min(f, len(shown) - 1)]]
        i = shown[min(f, len(shown) - 1)] + 1
        parts = [rf"\mathrm{{symmetries}}\ {g['order']}"]
        if g["mirrors"]:
            parts.append(rf"\mathrm{{mirrors}}\ {g['mirrors']}")
        if g["glides"]:
            parts.append(rf"\mathrm{{glides}}\ {g['glides']}")
        texts.append(rf"$\mathbf{{{g['name']}}}\ \ \cdot\ \ "
                     + r"\ \cdot\ ".join(parts)
                     + rf"\ \ \cdot\ \ {i}/{total}$")
    return {
        "scrim": {"rgb": [4, 6, 16],
                  "top": {"extent": 0.25, "strength": 0.95},
                  "bottom": {"extent": 0.14, "strength": 0.62}},
        "static": [
            {"text": LEAD,  "y": 0.944, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 20},
            {"text": CLAIM, "y": 0.908, "rgba": [1.0, 0.82, 0.34, 0.94], "size": 19},
            {"text": WHO,   "y": 0.874, "rgba": [0.45, 0.92, 1.0, 0.84], "size": 16},
        ],
        "dynamic": {"y": 0.836, "rgba": [1.0, 0.86, 0.50, 0.96], "size": 18,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 los 17 grupos de papel tapiz ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "wallpaper.py"), "--",
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
    print(f"[{NAME}] Subir con: python upload_wallpaper_short.py")


if __name__ == "__main__":
    main()
