"""
Short 9:16 — Empaquetamiento apolineo y el teorema de Descartes (15s @ 60 fps).

Aparecen las circunferencias de mayor a menor, con su curvatura entera rotulada
en las mas grandes. NO es un loop: termina en el empaquetamiento completo.

Musica: drone calmo, la familia ambiente del canal.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_apollonian"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "enlightened_drift"
FRAMES = "900"
RES = "1920"
FPS = "60"
KMAX = 900.0
HOLD = 90

DESCARTES = r"$(k_1+k_2+k_3+k_4)^2 = 2\,(k_1^2+k_2^2+k_3^2+k_4^2)$"
SOLVED = r"$k_4 = k_1+k_2+k_3 \pm 2\sqrt{k_1k_2+k_2k_3+k_3k_1}$"
INTEGERS = r"$\mathrm{start\ with\ integers} \Rightarrow \mathrm{every}\ k\ \mathrm{is\ an\ integer}$"


def overlay_spec():
    frames = int(FRAMES)
    reveal = max(1, frames - HOLD)
    texts = []
    for f in range(frames):
        p = min(1.0, (f + 1) / reveal)
        n = max(4, int(2909 * p ** 1.7))
        digits = f"{n:,}".replace(",", r"\,")
        texts.append(rf"${digits}\ \mathrm{{circles}}$")
    return {
        "scrim": {"rgb": [10, 13, 30],
                  "top": {"extent": 0.26, "strength": 0.92},
                  "bottom": {"extent": 0.20, "strength": 0.88}},
        "static": [
            {"text": DESCARTES, "y": 0.928, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 23},
            {"text": SOLVED,    "y": 0.884, "rgba": [1.0, 0.84, 0.36, 0.92], "size": 21},
            {"text": INTEGERS,  "y": 0.845, "rgba": [0.45, 0.92, 1.0, 0.86], "size": 18},
        ],
        "dynamic": {"y": 0.806, "rgba": [1.0, 0.86, 0.42, 0.95], "size": 25,
                    "texts": texts},
    }


def main():
    music = find_track(MUSIC_TRACK)
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 empaquetamiento apolineo ===")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "apollonian.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16", "--kmax", str(KMAX), "--hold", str(HOLD),
    ])
    if r.returncode != 0:
        sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME, "--skip-render", "--attractor", "clifford",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--format", "9:16", "--music", music,
    ])
    if r.returncode != 0:
        sys.exit("Error en build_clip.")

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
    print(f"[{NAME}] Subir con: python upload_apollonian_short.py")


if __name__ == "__main__":
    main()
