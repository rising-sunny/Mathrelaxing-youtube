"""
Short 9:16 — El iman de Ising: medio millon de espines (15s).

Caliente, critico (Tc de Onsager), frio, avalancha contra un campo y
recalentado. Metropolis en Taichi.

Musica: partitura "critical" de audio/orchestra.py (FluidSynth + MuseScore General).
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_ising"
OUTDIR = os.path.join(REPO, "output", NAME)
EVENTS = os.path.join(REPO, "data", f"{NAME}_events.json")

MUSIC_SCORE = "critical"
FRAMES = "900"
RES = "1920"
FPS = "60"



def overlay_spec():
    frames = int(FRAMES)
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    nsp = (ev["w"] // 2) * (ev["h"] // 2)
    lead = (rf"$\mathrm{{Ising\ magnet\ \cdot\ {nsp:,}\ spins}}$").replace(",", "{,}")
    law = (r"$H=-J\sum_{\langle ij\rangle}s_i s_j\ -\ h\sum_i s_i$")
    note = r"$T_c=\frac{2}{\ln(1+\sqrt{2})}=2.269\ \ \mathrm{(Onsager\ 1944)}$"
    fps = ev["fps"]
    tf = ev["t_field"]
    texts = []
    for f in range(frames):
        t = f / fps
        sh = ev["shown"][min(f, len(ev["shown"]) - 1)]
        T, M = sh["T"], sh["M"]
        if t < 5.3:
            lab = r"\mathrm{HOT:\ pure\ noise}" if t < 2.5 else r"\mathrm{cooling}"
        elif t < 7.0:
            lab = r"T=T_c:\ \mathrm{fractals\ at\ every\ scale}"
        elif t < tf:
            lab = r"\mathrm{COLD:\ order\ wins}"
        elif t < 12.6:
            lab = r"\mathrm{field\ AGAINST\ it:\ avalanche}"
        else:
            lab = r"\mathrm{heat\ melts\ the\ order}"
        texts.append(rf"${lab}\ \ \cdot\ \ T={T:.2f}\ \ M={M:+.2f}$")
    return {
        "scrim": {"rgb": [4, 5, 12],
                  "top": {"extent": 0.08, "strength": 0.80, "hold": 0.13},
                  "bottom": {"extent": 0.10, "strength": 0.60}},
        "static": [
            {"text": lead, "y": 0.946, "rgba": [1.0, 1.0, 1.0, 0.95], "size": 17},
            {"text": law,  "y": 0.900, "rgba": [1.0, 0.80, 0.45, 0.95], "size": 19},
            {"text": note, "y": 0.856, "rgba": [0.80, 0.88, 1.0, 0.88], "size": 15},
        ],
        "dynamic": {"y": 0.818, "rgba": [1.0, 0.82, 0.50, 0.96], "size": 16,
                    "texts": texts},
    }


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 Ising ===")

    if "--skip-scene" not in sys.argv:
        r = subprocess.run([
            sys.executable, os.path.join(REPO, "scenes", "ising.py"), "--",
            "--frames", FRAMES, "--res", RES, "--fps", FPS,
            "--name", NAME,
        ])
        if r.returncode != 0:
            sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "audio", "orchestra.py"),
        "--score", MUSIC_SCORE, "--outdir", OUTDIR,
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
