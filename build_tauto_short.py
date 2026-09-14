"""
Short 9:16 — Tautocrona: la cicloide donde todas llegan a la vez (15s @ 60 fps).

Dos cuencos de la misma profundidad y el mismo ancho, uno circular y uno
cicloidal, con seis cuentas soltadas juntas desde seis alturas distintas. En el
circulo se desfasan; en la cicloide no, nunca.

La cicloide cumple exactamente 4 oscilaciones en el clip, asi que ese cuenco
cierra en loop; el circular no, porque su periodo depende de la amplitud.

Musica: preset "horizon" de audio/ambient_score.py — Do menor con progresion.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_tauto"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "horizon"
FRAMES = "900"
RES = "1920"
FPS = "60"

SHM = r"$h=\frac{\sigma^{2}}{8r}\ \Rightarrow\ \ddot{\sigma}=-\frac{g}{4r}\,\sigma$"
PERIOD = r"$T=4\pi\sqrt{r/g}\quad\mathrm{whatever\ the\ amplitude}$"
FAIR = r"$\mathrm{both\ bowls:\ same\ depth,\ same\ width}$"


def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        sp = json.load(fh)["spreads"]
    texts = []
    for f in range(frames):
        sc, sy = sp[min(f, len(sp) - 1)]
        texts.append(rf"$\mathrm{{gap\ at\ the\ bottom:}}\ \ \mathrm{{circle}}\ "
                     rf"{sc:.3f}\,\mathrm{{s}}\ \ \cdot\ \ \mathrm{{cycloid}}\ "
                     rf"{sy:.3f}\,\mathrm{{s}}$")
    return {
        "scrim": {"rgb": [5, 6, 18],
                  "top": {"extent": 0.27, "strength": 0.93},
                  "bottom": {"extent": 0.12, "strength": 0.52}},
        "static": [
            {"text": SHM,    "y": 0.932, "rgba": [1.0, 1.0, 1.0, 0.96], "size": 24},
            {"text": PERIOD, "y": 0.884, "rgba": [1.0, 0.82, 0.34, 0.93], "size": 18},
            {"text": FAIR,   "y": 0.847, "rgba": [0.45, 0.92, 1.0, 0.86], "size": 16},
        ],
        "dynamic": {"y": 0.808, "rgba": [1.0, 0.80, 0.36, 0.95], "size": 17,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 tautocrona ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "tautochrone.py"), "--",
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
    print(f"[{NAME}] Subir con: python upload_tauto_short.py")


if __name__ == "__main__":
    main()
