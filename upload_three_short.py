"""Sube el short 'Tres distancias' (15s, 1080x1920) PROGRAMADO.

    python upload_three_short.py
    python upload_three_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_three", "shorts_three_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_three_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Only Three Gap Sizes. Ever. 🧵 The Three-Distance Theorem #math #shorts"

BODY_TMPL = (
    "Take a number α, walk around a circle of circumference 1 in steps of α, "
    "and drop a point everywhere you land: α, 2α, 3α, and so on up to Nα. "
    "The points scatter around the circle without ever repeating.\n\n"
    "Now measure the gaps between neighbouring points. You would expect a "
    "mess — N points, N gaps, all different. Instead there are at most "
    "THREE different gap lengths. Not roughly three. Three, for every single "
    "N, for every irrational α.\n\n"
    "And when there are three, the longest one is exactly the other two "
    "added together.\n\n"
    "Every row here is one value of N, with each gap coloured by which of "
    "the three lengths it is — teal for the shortest, plum for the middle, "
    "amber for the longest. The rows stack from N = 1 at the top down to "
    "N = {nmax} at the bottom, and only ever three colours appear in any of "
    "them. Of those {nmax} rows, {three} have three lengths and the rest "
    "have two; checked here, none has four.\n\n"
    "The weave you end up looking at is the continued fraction of α made "
    "visible. The rows where the middle length vanishes and only two survive "
    "are the moments the points are spread as evenly as they can be, and for "
    "the golden ratio used here they land at N = 1, 2, 4, 7, 12, 20, 33, 54, "
    "88, 143, 232, 376 — exactly one less than each Fibonacci number.\n\n"
    "Hugo Steinhaus conjectured it in the 1950s and it was proved "
    "independently several times over the next few years. It is one of those "
    "results that sounds like it cannot be true until you watch it refuse to "
    "break."
)

TAGS_EXTRA = [
    "three distance theorem", "steinhaus", "diophantine approximation",
    "continued fractions", "golden ratio", "number theory", "fibonacci",
    "equidistribution", "irrational numbers", "modular arithmetic",
    "three gap theorem", "self similarity",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    return BODY_TMPL.format(nmax=ev["nmax"], three=ev["rows_with_three"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_three_short.py")

    description = build_description(
        body(), hashtags=["#numbertheory", "#goldenratio", "#fibonacci", "#patterns"]
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
    if publish_at:
        print(f"Se publica : {publish_at}  (= {PUBLISH_HOUR:02d}:00 Chile)")

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
