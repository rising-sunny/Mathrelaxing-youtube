"""
Short 9:16 — Espiral de primos de Sacks (15s @ 60 fps, 1080x1920).

Cada entero en polares con radio sqrt(n) y angulo 2*pi*sqrt(n). Los primos se
acomodan en arcos en vez de repartirse al azar, y el polinomio de Euler
n^2+n+41 va resaltado: es el arco que da 40 primos seguidos.

Musica: drone theta, la misma familia hipnotica de los fractales.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_primes"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "new_beginning"
FRAMES = "900"
RES = "1920"
FPS = "60"
NMAX = 150_000
NMIN = 300

SACKS = r"$r=\sqrt{n} \qquad \theta = 2\pi\sqrt{n}$"
EULER = r"$n^2 + n + 41 \ \ \mathrm{is\ prime\ for}\ \ 0 \leq n \leq 39$"
LEGEND = r"$\mathrm{gold = prime} \quad \mathrm{cyan = Euler's\ polynomial}$"


def overlay_spec():
    """El contador sigue la misma rampa exponencial de numeros que la escena."""
    frames = int(FRAMES)
    ratio = (NMAX / NMIN) ** (1.0 / max(1, frames - 1))
    texts = []
    for f in range(frames):
        cur = int(min(NMAX, NMIN * ratio ** f))
        digits = f"{cur:,}".replace(",", r"\,")     # separador fino, estilo ISO
        texts.append(rf"$n \leq {digits}$")
    return {
        # La escena llena el cuadro: sin degradado las formulas no se leen.
        "scrim": {"rgb": [10, 13, 32],
                  "top": {"extent": 0.26, "strength": 0.92},
                  "bottom": {"extent": 0.20, "strength": 0.88}},
        "static": [
            {"text": SACKS,  "y": 0.925, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 29},
            {"text": EULER,  "y": 0.884, "rgba": [0.45, 1.0, 0.95, 0.92], "size": 24},
            {"text": LEGEND, "y": 0.846, "rgba": [0.72, 0.80, 1.0, 0.80], "size": 19},
        ],
        "dynamic": {"y": 0.806, "rgba": [1.0, 0.86, 0.42, 0.95], "size": 25,
                    "texts": texts},
    }


def main():
    music = find_track(MUSIC_TRACK)
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 espiral de primos ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080x1920 | hasta n={NMAX:,}")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "prime_spiral.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16",
        "--nmax", str(NMAX), "--nmin", str(NMIN),
    ])
    if r.returncode != 0:
        sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME, "--skip-render",
        "--attractor", "clifford",   # perfil de audio suave, sin percusion dura
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
        "-i", with_math, "-o", branded,
        "--cta-y", "0.795", "--handle-y", "0.028",
    ])
    if r.returncode != 0:
        sys.exit("Error quemando el CTA.")

    print(f"\n[{NAME}] LISTO -> {branded}")
    print(f"[{NAME}] Subir con: python upload_primes_short.py")


if __name__ == "__main__":
    main()
