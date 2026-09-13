"""
Short 9:16 — Mapa del gato de Arnold (15s @ 60 fps).

Una imagen se destruye con una regla de una linea y vuelve EXACTA en el paso
140. Verificado: 0 niveles de diferencia contra la original.

Musica: preset "lattice" de audio/ambient_score.py — La menor con ostinato de
corcheas. Una permutacion que vuelve a su punto de partida pide relojeria.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_catmap"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "lattice"
FRAMES = "900"
RES = "1920"
FPS = "60"


def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    n, period, sf = ev["n"], ev["period"], ev["step_frames"]
    rule = (rf"$(x,y)\mapsto(2x+y,\;x+y)\ \ \mathrm{{mod}}\ {n}$")
    lam = (r"$\lambda=\frac{3+\sqrt{5}}{2}=\varphi^{2}\approx 2.618"
           r"\ \ \mathrm{stretch\ per\ step}$")
    det = r"$\det=1:\ \mathrm{not\ one\ pixel\ is\ created\ or\ lost}$"

    hs = ev["hold_start"]
    texts = []
    for f in range(frames):
        k = min(period, max(0, f - hs) // sf)
        if f >= ev["return_frame"]:
            texts.append(rf"$\mathrm{{step}}\ {period}\,/\,{period}"
                         rf"\ \ \mathrm{{exactly\ the\ original}}$")
        else:
            texts.append(rf"$\mathrm{{step}}\ {k}\,/\,{period}$")
    return {
        "scrim": {"rgb": [6, 7, 20],
                  "top": {"extent": 0.26, "strength": 0.93},
                  "bottom": {"extent": 0.12, "strength": 0.55}},
        "static": [
            {"text": rule, "y": 0.930, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 22},
            {"text": lam,  "y": 0.884, "rgba": [1.0, 0.82, 0.34, 0.93], "size": 17},
            {"text": det,  "y": 0.845, "rgba": [0.45, 0.92, 1.0, 0.86], "size": 16},
        ],
        "dynamic": {"y": 0.806, "rgba": [1.0, 0.80, 0.36, 0.95], "size": 21,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 mapa del gato de Arnold ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "cat_map.py"), "--",
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
    print(f"[{NAME}] Subir con: python upload_catmap_short.py")


if __name__ == "__main__":
    main()
