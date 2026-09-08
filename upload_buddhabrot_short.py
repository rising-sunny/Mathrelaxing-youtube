"""Sube el short 'Buddhabrot' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para las 08:00 hora de Chile del dia siguiente.

    python upload_buddhabrot_short.py
    python upload_buddhabrot_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_buddhabrot", "shorts_buddhabrot_branded.mp4")

# Chile: UTC-4 en invierno (abr-sep), UTC-3 en verano (sep-abr).
CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "The Mandelbrot Set Is Hiding a Ghost 👻 The Buddhabrot #math #shorts"

BODY = (
    "You have seen the Mandelbrot set a thousand times. This is what it looks "
    "like from the inside out.\n\n"
    "The usual picture asks one question of every point: does z → z² + c run "
    "away to infinity, yes or no? Colour it in and you get that famous "
    "silhouette. The Buddhabrot asks a different question — not WHICH points "
    "escape, but WHERE THEY GO on the way out. Every orbit that escapes leaves "
    "a trail, every square it passes through gets one more count, and the "
    "orbits that never escape are thrown away entirely.\n\n"
    "What builds up is not a shape, it is a probability cloud: how often the "
    "escaping paths visit each part of the plane. That is why it looks like "
    "smoke instead of a boundary, and why it takes millions of orbits to see. "
    "Nine million of them here.\n\n"
    "The colour separates orbit lengths. Blue paths escaped within 50 steps and "
    "fill the body; red ones survived up to 5000 and draw the fine filaments. "
    "The figure is turned 90° from the usual Mandelbrot orientation — which is "
    "how it earned the name.\n\n"
    "Melinda Green discovered it in 1993. The name came later, from how the "
    "sideways figure looks."
)

TAGS_EXTRA = [
    "buddhabrot", "mandelbrot", "mandelbrot set", "fractal", "complex numbers",
    "chaos", "melinda green", "nebulabrot", "escape orbits", "probability",
    "mathematics", "fractal art", "monte carlo", "iteration",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_buddhabrot_short.py")

    description = build_description(
        BODY, hashtags=["#mandelbrot", "#fractal", "#buddhabrot", "#chaos"]
    )
    tags = build_tags(TAGS_EXTRA)

    if a.now:
        publish_at, privacy = None, "unlisted"
    else:
        publish_at = a.publish_at or _default_publish_at()
        privacy = "private"

    size_mb = os.path.getsize(VIDEO) / (1024 * 1024)
    print(f"Video      : {os.path.basename(VIDEO)} ({size_mb:.1f} MB)")
    print(f"Titulo     : {TITLE}")
    print(f"Privacidad : {privacy}")
    if publish_at:
        print(f"Se publica : {publish_at}  (= {PUBLISH_HOUR:02d}:00 Chile)")

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
