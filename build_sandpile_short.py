"""
Short 9:16 — Pila de arena abeliana (15s @ 60 fps, 1080x1920).

Un millon de granos sobre una sola celda. Regla unica: 4 granos colapsan y
reparten uno a cada vecino. El estado final es unico (teorema abeliano) y es
un fractal. La camara sigue el radio de la pila, asi que el tamano aparente
queda fijo y lo que se ve es la estructura refinandose a toda escala.

Musica: drone calmo, la misma familia ambiente del canal.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_sandpile"
OUTDIR = os.path.join(REPO, "output", NAME)

MUSIC_TRACK = "enlightened_drift"
GRAINS = "500000"
FRAMES = "900"
RES = "1920"
FPS = "60"


# Regla de colapso, identidad que da nombre al modelo (con glosa: sola es
# criptica) y contador de granos. Todo por encima de 0.80: el disco ocupa el
# cuadrado central del 9:16 y la banda de abajo queda para el CTA.
RULE = r"$z_v \geq 4 \ \Longrightarrow\ z_v \mapsto z_v - 4$"
RULE_2 = r"$z_u \mapsto z_u + 1 \quad \forall\, u \sim v$"
ABELIAN = r"$a_i\,a_j = a_j\,a_i \quad \mathrm{(the\ order\ never\ matters)}$"


def overlay_spec():
    """Lineas del overlay. El contador replica la curva N(f) de la escena."""
    frames, grains, hold = int(FRAMES), int(GRAINS), 45
    texts = []
    for f in range(frames):
        p = min(1.0, (f + 1) / max(1, frames - hold))
        n = max(1, int(grains * p * p))
        digits = f"{n:,}".replace(",", r"\,")     # separador fino, estilo ISO
        texts.append(rf"$N = {digits}\ \mathrm{{grains}}$")
    return {
        "static": [
            {"text": RULE,    "y": 0.925, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 30},
            {"text": RULE_2,  "y": 0.884, "rgba": [1.0, 0.90, 0.55, 0.88], "size": 26},
            {"text": ABELIAN, "y": 0.846, "rgba": [0.66, 0.76, 1.0, 0.85], "size": 22},
        ],
        "dynamic": {"y": 0.806, "rgba": [1.0, 0.86, 0.42, 0.95], "size": 25,
                    "texts": texts},
    }


def main():
    music = find_track(MUSIC_TRACK)

    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 Pila de arena abeliana ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080x1920 | {int(GRAINS):,} granos")

    # La escena acepta --grains, que build_clip no reenvia: se renderiza aparte
    # y build_clip solo arma audio + mux sobre los frames ya escritos.
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "abelian_sandpile.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16", "--grains", GRAINS,
    ])
    if r.returncode != 0:
        sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME,
        "--skip-render",
        "--attractor", "chladni",   # resonancia de placa: el perfil mas cercano a la arena
        "--frames", FRAMES,
        "--res", RES,
        "--fps", FPS,
        "--format", "9:16",
        "--music", music,
    ])
    if r.returncode != 0:
        sys.exit("Error en build_clip.")

    # 3) Overlay matematico en Computer Modern sobre la banda oscura de arriba.
    # No se usa el --math-overlay de build_clip: ese re-simula un atractor por
    # frame y aca la escena no es una EDO.
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

    # 4) CTA de suscripcion: abajo, en la banda que deja libre el disco.
    branded = os.path.join(OUTDIR, f"{NAME}_branded.mp4")
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "tools", "brand_cta.py"),
        "-i", with_math, "-o", branded,
        "--cta-y", "0.795", "--handle-y", "0.028",
    ])
    if r.returncode != 0:
        sys.exit("Error quemando el CTA.")

    print(f"\n[{NAME}] LISTO -> {branded}")
    print(f"[{NAME}] Subir con: python upload_sandpile_short.py")


if __name__ == "__main__":
    main()
