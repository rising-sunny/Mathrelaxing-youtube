"""
Short 9:16 — Teselado hiperbolico {3,7} en el disco de Poincare (15s @ 60 fps).

Infinitos triangulos, todos del mismo tamano: parecen encogerse hacia el borde
solo porque el disco es un mapa plano de un espacio curvo. Rotacion hiperbolica
de 2*pi alrededor de un punto fuera del centro, asi que el loop cierra exacto.

Musica: la misma pista del short de Clifford, su pariente geometrico.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_hyperbolic"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "betawaves"
FRAMES = "900"
RES = "1920"
FPS = "60"
P, Q = 3, 7

# La metrica es la explicacion de todo el video: el factor 2/(1-|z|^2) diverge
# en el borde, asi que las astillas del anillo son piezas de tamano normal.
METRIC = r"$ds = \frac{2\,|dz|}{1-|z|^{2}}$"
TILING = rf"$\{{{P},{Q}\}}: \ {Q}\ \mathrm{{triangles\ at\ every\ vertex}}$"
ANGLES = r"$\alpha + \beta + \gamma < \pi \quad \mathrm{(impossible\ on\ a\ flat\ plane)}$"


def overlay_spec():
    frames = int(FRAMES)
    texts = [rf"$\theta = {360.0 * f / frames:5.1f}^\circ$" for f in range(frames)]
    return {
        # La escena llena el cuadro: sin degradado las formulas no se leen.
        "scrim": {"rgb": [10, 13, 32],
                  "top": {"extent": 0.26, "strength": 0.92},
                  "bottom": {"extent": 0.20, "strength": 0.88}},
        "static": [
            {"text": METRIC, "y": 0.928, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 30},
            {"text": TILING, "y": 0.881, "rgba": [0.45, 0.97, 1.0, 0.92], "size": 24},
            {"text": ANGLES, "y": 0.845, "rgba": [1.0, 0.84, 0.42, 0.85], "size": 19},
        ],
        "dynamic": {"y": 0.806, "rgba": [1.0, 0.86, 0.42, 0.95], "size": 25,
                    "texts": texts},
    }


def main():
    music = find_track(MUSIC_TRACK)
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 teselado hiperbolico {{{P},{Q}}} ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080x1920 | loop exacto")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "hyperbolic_tiling.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16", "--p", str(P), "--q", str(Q),
    ])
    if r.returncode != 0:
        sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME, "--skip-render",
        "--attractor", "clifford",   # perfil suave, sin percusion dura
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
    print(f"[{NAME}] Subir con: python upload_hyperbolic_short.py")


if __name__ == "__main__":
    main()
