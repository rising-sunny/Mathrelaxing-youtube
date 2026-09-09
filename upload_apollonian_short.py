"""Sube el short 'Apolineo' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para las 08:00 hora de Chile del dia siguiente.

    python upload_apollonian_short.py
    python upload_apollonian_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_apollonian", "shorts_apollonian_branded.mp4")

# Chile: UTC-4 en invierno (abr-sep), UTC-3 en verano (sep-abr).
CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Every Circle Here Is a Whole Number 🔵 Apollonian Gasket #math #shorts"

BODY = (
    "Three circles touching each other leave two gaps, and each gap fits "
    "exactly one new circle touching all three. Do it forever and you get "
    "this. But look at the labels.\n\n"
    "Each number is the circle's curvature — one divided by its radius. The "
    "big ones are 2, 2, 3, 3, then 6, 6, 11, 11, and it never stops being a "
    "whole number. Not rounded. Exact, all 2,909 of them.\n\n"
    "Descartes found the reason in 1643, in a letter to a princess. For any "
    "four mutually touching circles:\n\n"
    "(k₁+k₂+k₃+k₄)² = 2(k₁²+k₂²+k₃²+k₄²)\n\n"
    "Solve it for the new circle and you get a square root — which should ruin "
    "everything, since square roots are rarely whole. But the equation is a "
    "quadratic, so it has two solutions, and one of them is the circle you "
    "already had. Subtract them and the root cancels:\n\n"
    "k₄′ = 2(k₁+k₂+k₃) − k₄\n\n"
    "Only addition and subtraction survive. Start with whole numbers and you "
    "can never leave them. The outer circle counts as −1 because it curves the "
    "other way, wrapping the rest instead of being wrapped."
)

TAGS_EXTRA = [
    "apollonian gasket", "descartes circle theorem", "circle packing",
    "integer curvature", "number theory", "fractal", "tangent circles",
    "geometry", "descartes", "kissing circles", "mathematics", "integers",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_apollonian_short.py")

    description = build_description(
        BODY, hashtags=["#apollonian", "#geometry", "#numbertheory", "#fractal"]
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
