"""Sube el short 'Ramsey' (15s, 1080x1920) PROGRAMADO.

    python upload_ramsey_short.py
    python upload_ramsey_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_ramsey", "shorts_ramsey_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_ramsey_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "In Any Group of Six, This Always Happens 🔺 R(3,3) = 6 #math #shorts"

BODY_TMPL = (
    "Put six people in a room. Join every pair with a line: red if they know "
    "each other, blue if they do not. There are {k6:,} ways to do that.\n\n"
    "In every single one of them you will find a triangle of one colour — "
    "three people who all know each other, or three who are all strangers. "
    "Not usually. Always.\n\n"
    "With five people you can dodge it. Of the {k5:,} colourings of the "
    "five-point graph, {k5free} have no monochromatic triangle at all: draw "
    "the pentagon in one colour and the pentagram inside it in the other and "
    "nothing matches. That is the colouring you see at the start.\n\n"
    "Add the sixth point and every escape disappears. All {k6:,} colourings "
    "were enumerated for this video and none of them is free. It is not even "
    "close: the fewest monochromatic triangles any colouring of six points "
    "can have is {k6min}, and the average is {k6mean:.0f}.\n\n"
    "The proof fits in three lines and needs no computer. Pick any point. "
    "Five edges leave it, two colours, so at least three of them share a "
    "colour — that is the pigeonhole principle. Look at those three "
    "neighbours. If any two of them are joined in that same colour, you have "
    "your triangle. If none are, then those three are joined to each other "
    "entirely in the other colour, and that is your triangle instead. There "
    "is nowhere left to go.\n\n"
    "This is the smallest Ramsey number, R(3,3) = 6. The next one, R(4,4), "
    "is 18. Nobody knows R(5,5); it is somewhere between 43 and 46, and "
    "Erdős liked to say that if aliens demanded R(5,5) we should compute it, "
    "but if they demanded R(6,6) we should attack first.\n\n"
    "The bars along the bottom log every colouring shown, one bar each, "
    "height equal to how many monochromatic triangles it has. The green "
    "marks at the left are the five-point escapes. After the sixth point "
    "arrives, no bar ever touches the floor again."
)

TAGS_EXTRA = [
    "ramsey theory", "ramsey number", "graph theory", "combinatorics",
    "pigeonhole principle", "erdos", "discrete mathematics", "proof",
    "complete graph", "friends and strangers", "party problem",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    return BODY_TMPL.format(k5=ev["k5_total"], k5free=ev["k5_free"],
                            k6=ev["k6_total"], k6min=ev["k6_min"],
                            k6mean=ev["k6_mean"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_ramsey_short.py")

    description = build_description(
        body(), hashtags=["#graphtheory", "#combinatorics", "#ramsey", "#proof"]
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
