"""
Short 9:16 — Arbol recursivo al atardecer (15s @ 60 fps, 1080x1920).

Pieza de ambiente: paleta calida, imagen figurativa y SIN overlay de formulas.
Es un registro distinto al resto del canal a proposito, asi que no pasa por
tools/latex_overlay.py ni por brand_cta: no lleva NINGUN texto quemado.

Todo el movimiento es periodico, asi que el loop cierra exacto.

Musica: composicion generativa propia (audio/autumn_score.py), no una
pista licenciada: A|b maj9 con campanas pentatonicas, periodica de 15s.
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_autumn"
OUTDIR = os.path.join(REPO, "output", NAME)

FRAMES = "900"
RES = "1920"
FPS = "60"


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 arbol recursivo al atardecer ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080x1920 | loop exacto")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "autumn_tree.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16",
    ])
    if r.returncode != 0:
        sys.exit("Error renderizando la escena.")

    # 2) Musica: composicion propia y periodica (audio/autumn_score.py). No se
    # usa el drone generico de build_audio: son cinco senoidales pensadas como
    # colchon debajo de golpes de simulacion, no como pieza.
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "audio", "autumn_score.py"),
        "--outdir", OUTDIR, "--duration", str(int(FRAMES) / int(FPS)),
    ])
    if r.returncode != 0:
        sys.exit("Error componiendo la musica.")

    # 3) Frames + musica. Sin overlay de formulas y SIN texto quemado: en este
    # registro el CTA en pantalla rompe la pieza, y va solo en la descripcion.
    final = os.path.join(OUTDIR, f"{NAME}.mp4")
    r = subprocess.run([
        "ffmpeg", "-y", "-framerate", FPS,
        "-i", os.path.join(OUTDIR, "frames", "%04d.png"),
        "-i", os.path.join(OUTDIR, "music.wav"),
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k", "-shortest", final,
    ])
    if r.returncode != 0:
        sys.exit("Error en el ensamblaje final.")

    print(f"\n[{NAME}] LISTO -> {final}")
    print(f"[{NAME}] Subir con: python upload_autumn_short.py")


if __name__ == "__main__":
    main()
