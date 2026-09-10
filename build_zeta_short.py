"""
Short 9:16 — La funcion zeta de Riemann sobre la franja critica (15s @ 60 fps).

La camara sube por la recta Re(s) = 1/2 y cada cero destella al cruzar el
centro del cuadro, con su nota. NO es un loop: recorre t de 9.4 a 48.6.

Musica: si la pista licenciada esta disponible se usa esa; si no, el drone
sintetizado de build_clip. En los dos casos los ceros suenan encima, sonificados
desde data/shorts_zeta_events.json.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

NAME = "shorts_zeta"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_TRACK = "how_did_we_get_here"
FRAMES = "900"
RES = "1920"
FPS = "60"

SERIES = r"$\zeta(s)=\sum_{n=1}^{\infty} n^{-s}=\prod_{p\,\mathrm{prime}}\left(1-p^{-s}\right)^{-1}$"
CLAIM = r"$\mathrm{every\ zero\ found\ so\ far\ has}\ \ \mathrm{Re}(s)=1/2$"
OPEN = r"$\mathrm{Riemann,\ 1859\ \cdot\ still\ unproven}$"

HOLD_FRAMES = 70        # cuanto queda en pantalla el cero recien cruzado


def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        zeros = json.load(fh)["zeros"]

    # El encuadre de la escena, replicado: t en el centro del cuadro por frame.
    first, last = zeros[0], zeros[7]
    rate = (last["t"] - first["t"]) / (last["frame"] - first["frame"])
    c0 = first["t"] - first["frame"] * rate

    texts = []
    for f in range(frames):
        hit = None
        for z in zeros:
            if 0 <= f - z["frame"] < HOLD_FRAMES:
                hit = z
        if hit is not None:
            texts.append(rf"$\zeta(1/2+{hit['t']:.6f}\,i)=0$")
        else:
            texts.append(rf"$s=1/2+{c0 + rate * f:.3f}\,i$")
    return {
        "scrim": {"rgb": [8, 11, 26],
                  "top": {"extent": 0.26, "strength": 0.93},
                  "bottom": {"extent": 0.12, "strength": 0.55}},
        "static": [
            {"text": SERIES, "y": 0.928, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 21},
            {"text": CLAIM,  "y": 0.884, "rgba": [1.0, 0.84, 0.36, 0.92], "size": 19},
            {"text": OPEN,   "y": 0.847, "rgba": [0.45, 0.92, 1.0, 0.84], "size": 17},
        ],
        "dynamic": {"y": 0.808, "rgba": [1.0, 0.86, 0.42, 0.95], "size": 23,
                    "texts": texts},
    }


def main():
    # La pista licenciada no esta versionada en el repo: si falta, build_clip
    # sintetiza su drone y el short igual queda completo.
    music = find_track(MUSIC_TRACK, required=False)
    if music is None:
        print(f"[{NAME}] Sin '{MUSIC_TRACK}': se usa el drone sintetizado.")
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 zeta de Riemann ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "zeta_critical.py"), "--",
            "--frames", FRAMES, "--res", RES, "--fps", FPS,
            "--name", NAME, "--format", "9:16",
        ])
        if r.returncode != 0:
            sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", NAME, "--skip-render", "--attractor", "clifford",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--format", "9:16",
    ] + (["--music", music] if music else []))
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
    print(f"[{NAME}] Subir con: python upload_zeta_short.py")


if __name__ == "__main__":
    main()
