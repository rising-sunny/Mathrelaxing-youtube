"""Sube el short 'Mandelbrot zoom' (15s, 1080x1920).

Por defecto UNLISTED (para revisar). Con --publish-at o --thursday queda
programado para el jueves 2026-07-23 08:00 hora de Chile (= 12:00 UTC).

    python upload_mandelbrot_short.py             # unlisted, para revisar
    python upload_mandelbrot_short.py --thursday  # programado jueves 8am Chile
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_mandelbrot", "shorts_mandelbrot_branded.mp4")

CHILE_UTC_OFFSET = -4
THURSDAY_LOCAL = datetime(2026, 7, 23, 8, 0, 0)

TITLE = "2,500,000x Into the Mandelbrot Set 🌀✨ #math #shorts"

BODY = (
    "The entire Mandelbrot set comes from one line of math: z -> z*z + c, asked "
    "again and again. This is a 2,500,000x zoom into the edge of that set — the "
    "Seahorse Valley — and the detail never runs out. Spirals grow inside "
    "spirals, and every scale looks new.\n\n"
    "Then, near the bottom of the dive, a perfect miniature copy of the whole "
    "set appears out of nowhere. That infinite self-similarity from a single "
    "equation is why it became the most famous fractal ever found (Benoit "
    "Mandelbrot, 1980)."
)

TAGS_EXTRA = [
    "mandelbrot", "mandelbrot set", "fractal zoom", "fractal", "infinite zoom",
    "seahorse valley", "self similarity", "benoit mandelbrot", "complex numbers",
    "deep zoom",
]


def _thursday_utc() -> str:
    utc = THURSDAY_LOCAL - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--thursday", action="store_true", help="Programar jueves 08:00 Chile")
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC explicito")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}")

    description = build_description(
        BODY, hashtags=["#Mandelbrot", "#fractal", "#math", "#infinity"]
    )
    tags = build_tags(TAGS_EXTRA)

    if a.publish_at or a.thursday:
        publish_at = a.publish_at or _thursday_utc()
        privacy = "private"
    else:
        publish_at, privacy = None, "unlisted"

    size_mb = os.path.getsize(VIDEO) / (1024 * 1024)
    print(f"Video      : {os.path.basename(VIDEO)} ({size_mb:.1f} MB)")
    print(f"Titulo     : {TITLE}")
    print(f"Privacidad : {privacy}")
    if publish_at:
        print(f"Se publica : {publish_at}")

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
    print(f"\n\nSubido a '{channel_name}' como {privacy.upper()}")
    print(f"https://youtu.be/{video_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
