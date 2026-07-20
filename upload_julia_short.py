"""Sube el short 'Julia morph' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para el miercoles 2026-07-22 08:00 hora de Chile
(UTC-4 en julio) = 12:00 UTC.

    python upload_julia_short.py
    python upload_julia_short.py --publish-at 2026-07-22T13:00:00Z
    python upload_julia_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_julia", "shorts_julia_branded.mp4")

CHILE_UTC_OFFSET = -4  # julio = horario estandar en Chile
DEFAULT_LOCAL = datetime(2026, 7, 22, 8, 0, 0)

TITLE = "One Number Changes Everything: The Julia Set Morphing 🌀✨ #math #shorts"

BODY = (
    "Every frame here is the same rule — square the number, add c, repeat — "
    "run on two million points. The only thing changing is c, tracing a circle "
    "through the complex plane.\n\n"
    "That single moving number is enough to grow the fractal into branches, "
    "shatter it into dust, and rebuild it again. Because c returns to where it "
    "started, the whole shape loops back seamlessly. Discovered by Gaston Julia "
    "in 1918 — decades before any computer could draw it."
)

TAGS_EXTRA = [
    "julia set", "fractal", "mandelbrot", "complex numbers", "gaston julia",
    "fractal zoom", "generative", "chaos", "iteration", "numpy",
    "fractal animation", "mesmerizing",
]


def _default_publish_at() -> str:
    utc = DEFAULT_LOCAL - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n"
                 "Genera primero: python build_julia_short.py && "
                 "python tools/brand_cta.py -i output/shorts_julia/shorts_julia.mp4 "
                 "-o output/shorts_julia/shorts_julia_branded.mp4")

    description = build_description(
        BODY, hashtags=["#JuliaSet", "#fractal", "#complexnumbers", "#math"]
    )
    tags = build_tags(TAGS_EXTRA)

    if a.now:
        publish_at, privacy = None, "unlisted"
    else:
        publish_at = a.publish_at or _default_publish_at()
        privacy = "private"  # YouTube lo exige cuando hay publishAt

    size_mb = os.path.getsize(VIDEO) / (1024 * 1024)
    print(f"Video      : {os.path.basename(VIDEO)} ({size_mb:.1f} MB)")
    print(f"Titulo     : {TITLE}")
    print(f"Privacidad : {privacy}")
    if publish_at:
        print(f"Se publica : {publish_at}  (= miercoles 2026-07-22 08:00 Chile)")

    def on_progress(p):
        sys.stdout.write(f"\rSubiendo... {p}%")
        sys.stdout.flush()

    video_id, channel_name = upload_video_to_youtube(
        video_path=VIDEO,
        title=TITLE,
        description=description,
        tags=tags,
        privacy_status=privacy,
        desired_channel="MathRelaxing",
        publish_at=publish_at,
        progress_callback=on_progress,
    )
    print(f"\n\nSubido a '{channel_name}'")
    print(f"https://youtu.be/{video_id}")
    if publish_at:
        print(f"Programado: se hace publico solo el {publish_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
