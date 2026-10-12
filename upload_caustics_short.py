"""Sube el short 'Causticas' (15s, 1080x1920) PROGRAMADO.

    python upload_caustics_short.py
    python upload_caustics_short.py --now      # unlisted ya, sin programar
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_caustics",
                     "shorts_caustics_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_caustics_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Why Pool Floors Dance With Light ☀️ #physics #shorts"

BODY_TMPL = (
    "Those bright, wobbling lines on the bottom of every swimming pool have a "
    "name: caustics. Each one is a place where the surface of the water acts "
    "like a lens and focuses sunlight.\n\n"
    "Light bends when it enters water, by Snell's law:\n\n"
    "n1 sin(theta1) = n2 sin(theta2),   n = 1.333 for water\n\n"
    "A wave crest is a tiny magnifying glass. If the pool is deep enough, "
    "the light it gathers crosses over into a bright line. For a gentle wave "
    "of height A and wavenumber k, that first happens at the depth\n\n"
    "D = 1 / ((1 - 1/n) A k^2)\n\n"
    "Deeper than that, the lines fold over each other into the moving web "
    "you know from every pool. Mathematically they are folds and cusps, the "
    "same shapes catastrophe theory describes.\n\n"
    "Nothing here is painted. The water surface follows the wave equation, "
    "with a breeze, rain, a stone and a gust of wind. Then every pixel of "
    "sunlight is traced through the surface with the exact Snell's law and "
    "dropped onto the tiles; where many rays land, the floor glows. Even the "
    "music is tied to the water: every raindrop you see plays a note at the "
    "instant it hits.\n\n"
    "Checked before rendering: a ripple travels at {v:.3f} cells per step "
    "where the equation says {c}, and for a sine-shaped surface the first "
    "caustic appeared at depth {dm:.1f} against the formula's {dt:.1f}."
)

TAGS_EXTRA = [
    "caustics", "light", "optics", "snell's law", "refraction", "swimming pool",
    "pool light", "catastrophe theory", "wave equation", "ray tracing",
    "physics of light", "satisfying",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    v = ev["verify"]
    return BODY_TMPL.format(v=v["ring_speed"], c=v["c"], dm=v["focal_measured"],
                            dt=v["focal_theory"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_caustics_short.py")

    description = build_description(
        body(), hashtags=["#physics", "#light", "#optics", "#science"]
    )
    tags = build_tags(TAGS_EXTRA)

    if a.now:
        publish_at, privacy = None, "unlisted"
    else:
        publish_at = a.publish_at or _default_publish_at()
        privacy = "private"

    print(f"Video      : {os.path.basename(VIDEO)} "
          f"({os.path.getsize(VIDEO) / (1024 * 1024):.1f} MB)")
    print(f"Titulo     : {TITLE}")
    print(f"Privacidad : {privacy}")

    def on_progress(p):
        sys.stdout.write(f"\rSubiendo... {p}%")
        sys.stdout.flush()

    video_id, channel_name = upload_video_to_youtube(
        video_path=VIDEO, title=TITLE, description=description, tags=tags,
        privacy_status=privacy, desired_channel="MathRelaxing",
        publish_at=publish_at, progress_callback=on_progress,
    )
    print(f"\n\nSubido a '{channel_name}'")
    print(f"https://youtu.be/{video_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
