"""Sube el short 'Arbol de otono' (15s, 1080x1920) PROGRAMADO.

    python upload_autumn_short.py
    python upload_autumn_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_autumn", "shorts_autumn.mp4")

# Estas piezas de ambiente van al canal chico, no a MathRelaxing.
CHANNEL = "nostalgicmood"
CHANNEL_TITLE = "Nostalgic Mood"

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "One Rule Grew 11,542 Branches 🍂 Autumn at Sunset #shorts"

BODY = (
    "No tree here was drawn. One rule was: split, turn, shorten, repeat. Run it "
    "ten levels deep and 11,542 branches fall out of it, along with 3,563 "
    "leaves that let go on their own schedule.\n\n"
    "That is the whole trick behind how real trees look. A branch is a smaller "
    "copy of the trunk, a twig a smaller copy of the branch — self-similarity, "
    "the same property that builds every fractal. The shortening ratio is what "
    "decides whether you get an oak or a fern.\n\n"
    "The wind is one sine wave, scaled by how far each branch sits from the "
    "trunk, which is why the trunk barely moves and the tips swing. Every leaf "
    "falls on its own offset. It all repeats exactly, so the loop is seamless — "
    "this autumn never ends.\n\n"
    "The music is generated too: an A\u266d major ninth chord with bells "
    "moving through a pentatonic scale, written so every frequency completes "
    "a whole number of cycles in fifteen seconds. That is why it loops without "
    "a seam.\n\n"
    "Made entirely in Python. No 3D, no footage, no assets, no samples."
)

TAGS_EXTRA = [
    "generative art", "procedural art", "recursion", "fractal tree",
    "l-system", "autumn", "sunset", "relaxing", "ambient", "cozy",
    "creative coding", "python art", "lofi", "aesthetic",
    "generative music", "ambient music", "procedural audio",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_autumn_short.py")

    description = build_description(
        BODY, channel_name=CHANNEL, hashtags=["#autumn", "#generativeart", "#creativecoding", "#cozy"]
    )
    tags = build_tags(TAGS_EXTRA, channel_name=CHANNEL)

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
        video_path=VIDEO, title=TITLE, description=description, tags=tags,
        privacy_status=privacy, desired_channel=CHANNEL_TITLE,
        publish_at=publish_at, progress_callback=on_progress,
    )
    print(f"\n\nSubido a '{channel_name}'")
    print(f"https://youtu.be/{video_id}")
    if publish_at:
        print(f"Programado: se hace publico solo el {publish_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
