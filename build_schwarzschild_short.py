"""
Short 9:16 — Geodesicas de Schwarzschild alrededor de un agujero negro (15s @ 60 fps).

Particulas en el campo geodesico: rosetas que precesan porque la orbita no
cierra, orbitas zoom-whirl pegadas a la esfera de fotones y caidas que se
frenan y se apagan en el horizonte por el corrimiento al rojo. NO es un loop.

Musica: preset "horizon" de audio/ambient_score.py — Do menor con progresion
i-VI-iv-VII, pedal de Do fijo debajo, motivo melodico escrito y un golpe grave
en la costura del loop. No lleva los golpes sonificados de build_clip: aca la
musica es contenido, no acompanamiento.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_schwarzschild"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "horizon"
FRAMES = "900"
RES = "1920"
FPS = "60"

GEODESIC = (r"$\dfrac{d^2r}{d\tau^2}="
            r"-\dfrac{M}{r^2}+\dfrac{L^2}{r^3}-\dfrac{3ML^2}{r^4}$")
NEWTON = r"$\mathrm{Newton\ stops\ after\ two\ terms.\ The\ third\ is\ curvature.}$"
RADII = (r"$r=3M\ \mathrm{photon\ sphere}\ \cdot\ "
         r"r=6M\ \mathrm{last\ stable\ orbit}$")


def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        captured = json.load(fh)["captured"]
    texts = []
    for f in range(frames):
        n = captured[min(f, len(captured) - 1)]
        digits = f"{n:,}".replace(",", r"\,")
        texts.append(rf"${digits}\ \mathrm{{swallowed}}$")
    return {
        "scrim": {"rgb": [6, 8, 20],
                  "top": {"extent": 0.27, "strength": 0.90},
                  "bottom": {"extent": 0.12, "strength": 0.50}},
        "static": [
            {"text": GEODESIC, "y": 0.930, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 22},
            {"text": NEWTON,   "y": 0.874, "rgba": [1.0, 0.82, 0.34, 0.92], "size": 18},
            {"text": RADII,    "y": 0.841, "rgba": [0.45, 0.92, 1.0, 0.84], "size": 16},
        ],
        "dynamic": {"y": 0.804, "rgba": [1.0, 0.72, 0.30, 0.95], "size": 23,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 geodesicas de Schwarzschild ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "schwarzschild.py"), "--",
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

    clip_raw = os.path.join(OUTDIR, f"{NAME}.mp4")
    r = subprocess.run([
        "ffmpeg", "-y", "-framerate", FPS,
        "-i", os.path.join(OUTDIR, "frames", "%04d.png"),
        "-i", os.path.join(OUTDIR, "music.wav"),
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k", "-shortest", clip_raw,
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

    clip = os.path.join(OUTDIR, f"{NAME}.mp4")
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
    print(f"[{NAME}] Subir con: python upload_schwarzschild_short.py")


if __name__ == "__main__":
    main()
