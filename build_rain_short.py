"""
Short 9:16 — Lluvia sobre un vidrio (15s @ 60 fps, 1080x1920).

Tercera pieza del registro ambiental: interior y de cerca, contra el otono y la
aurora que son paisajes. Sin overlay de formulas y sin texto quemado.

Todo el movimiento es periodico en el ciclo, asi que el loop cierra exacto.

Musica: preset "rain" de audio/ambient_score.py — Sol menor con novena, con
mas campanas y mas juntas, para que dialoguen con las gotas.
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))

NAME = "shorts_rain"
OUTDIR = os.path.join(REPO, "output", NAME)

FRAMES = "900"
RES = "1920"
FPS = "60"


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"\n[{NAME}] === Short 9:16 lluvia sobre el vidrio ===")
    print(f"[{NAME}] {FRAMES} frames | {FPS} fps | 1080x1920 | loop exacto")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", "rain_window.py"), "--",
        "--frames", FRAMES, "--res", RES, "--fps", FPS,
        "--name", NAME, "--format", "9:16",
    ])
    if r.returncode != 0:
        sys.exit("Error renderizando la escena.")

    r = subprocess.run([
        sys.executable, os.path.join(REPO, "audio", "ambient_score.py"),
        "--preset", "rain", "--outdir", OUTDIR,
        "--duration", str(int(FRAMES) / int(FPS)),
    ])
    if r.returncode != 0:
        sys.exit("Error componiendo la musica.")

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
    print(f"[{NAME}] Subir con: python upload_aurora_short.py")


if __name__ == "__main__":
    main()
