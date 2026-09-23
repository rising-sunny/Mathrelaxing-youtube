"""
Short 9:16 — Luciernagas de Kuramoto: sincronizacion sin lider (15s).

Nueve mil osciladores con su propio ritmo; el acoplamiento sube y el
enjambre termina destellando junto, justo sobre el pulso de la musica.

Musica: preset "fireflies" de audio/ambient_score.py.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_kuramoto"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_PRESET = "fireflies"
FRAMES = "900"
RES = "1920"
FPS = "60"



def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    lead = (rf"$\mathrm{{Kuramoto\ model}}\ \cdot\ {ev['n']}\ "
            rf"\mathrm{{fireflies}}\ \cdot\ \mathrm{{no\ leader}}$")
    law = (r"$\dot\theta_i=\omega_i+K\,r\,\sin(\psi-\theta_i)$")
    note = r"$\mathrm{exact:}\ \ r=\sqrt{1-K_c/K}$"
    texts = []
    for f in range(frames):
        s = ev["shown"][min(f, len(ev["shown"]) - 1)]
        texts.append(rf"$K={s['k_over_kc']:.2f}\,K_c\ \ \cdot\ \ r={s['r']:.2f}"
                     rf"\ \ \cdot\ \ {s['locked']*100:.0f}\%\ \mathrm{{locked}}$")
    return {
        "scrim": {"rgb": [3, 5, 12],
                  "top": {"extent": 0.26, "strength": 0.96},
                  "bottom": {"extent": 0.16, "strength": 0.70}},
        "static": [
            {"text": lead, "y": 0.946, "rgba": [1.0, 1.0, 1.0, 0.95], "size": 17},
            {"text": law,  "y": 0.903, "rgba": [1.0, 0.80, 0.34, 0.95], "size": 21},
            {"text": note, "y": 0.865, "rgba": [0.62, 1.0, 0.40, 0.88], "size": 16},
        ],
        "dynamic": {"y": 0.825, "rgba": [1.0, 0.84, 0.42, 0.96], "size": 17,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 luciernagas de Kuramoto ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "kuramoto.py"), "--",
            "--frames", FRAMES, "--res", RES, "--fps", FPS,
            "--name", NAME,
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
        # loudnorm de una pasada va en modo dinamico y se pasa del techo:
        # con este preset dejaba el pico real en +0.9 dBFS, o sea recortando.
        # El limitador detras es la red de seguridad (0.84 = -1.5 dBFS).
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.84:level=false",
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
