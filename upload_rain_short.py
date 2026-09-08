"""Sube el short 'Lluvia sobre el vidrio' (15s, 1080x1920) PROGRAMADO.

    python upload_rain_short.py
    python upload_rain_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_rain", "shorts_rain.mp4")

# Estas piezas de ambiente van al canal chico, no a MathRelaxing.
CHANNEL = "nostalgicmood"
CHANNEL_TITLE = "Nostalgic Mood"

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Every Raindrop Is a Lens 🌧️ Rain on Glass at Night #shorts"

BODY = (
    "Look closely at any drop on the glass. The little world inside it is "
    "upside down.\n\n"
    "A drop of water sitting on a window is a convex lens, and a convex lens "
    "flips what it sees. So every drop here is painted by sampling the scene "
    "from BELOW where the drop actually sits — that one detail is what makes "
    "them read as water instead of bright dots. The rim glow and the small "
    "highlight up and to the left do the rest.\n\n"
    "The city behind is 27 lights thrown far out of focus. That is why they "
    "are discs and not points: a lens that cannot focus turns every point of "
    "light into a small image of its own aperture. The drops that slide down "
    "wipe the fog as they go and, for a moment, you can see through.\n\n"
    "Every motion repeats exactly every fifteen seconds — the drift of the "
    "lights, each falling drop, its own phase — so the loop has no seam. The "
    "music is generated the same way: a G minor ninth chord with bells on a "
    "pentatonic scale.\n\n"
    "Made entirely in Python. No 3D, no footage, no assets, no samples."
)

TAGS_EXTRA = [
    "rain", "rain on window", "rainy night", "bokeh", "city lights",
    "cozy", "relaxing", "sleep", "study", "lofi", "chill", "ambient",
    "generative art", "procedural art", "creative coding", "night",
    "generative music", "ambient music", "no copyright",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_rain_short.py")

    description = build_description(
        BODY, channel_name=CHANNEL, hashtags=["#rain", "#cozy", "#lofi", "#relaxing"]
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
