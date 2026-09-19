"""Sube el short 'Wallpaper' (15s, 1080x1920) PROGRAMADO.

    python upload_wallpaper_short.py
    python upload_wallpaper_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_wallpaper",
                     "shorts_wallpaper_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_wallpaper_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "There Are Exactly 17 Ways to Tile a Wall 🧱 Not 16, Not 18 #math #shorts"

BODY_TMPL = (
    "A wallpaper pattern can have all sorts of symmetry: it slides, it turns, "
    "it reflects, it glides. Ask how many genuinely different combinations of "
    "those are possible in a flat plane and the answer is not 'lots'. It is "
    "{total}.\n\n"
    "Seventeen, and that is the whole list. Every tiled floor, every fabric "
    "print, every Escher drawing, every pattern on the walls of the Alhambra "
    "is one of these {total}. Evgraf Fedorov proved it in 1891.\n\n"
    "They run here from least symmetric to most. p1 at the start only slides "
    "— no turn, no mirror, nothing else. p6m at the end has twelve: six-fold "
    "rotation and six mirror lines. The label tracks what each one actually "
    "has, counted from the group itself.\n\n"
    "Nothing here is drawn by hand or copied from a reference. Each pattern "
    "is built by taking one lopsided blob of a motif and averaging it over "
    "its group — sum the motif over every symmetry and you get a function "
    "that is invariant because it cannot be anything else. The result is "
    "exact: checked at three thousand random points, every pattern matches "
    "itself under its own symmetries to fifteen decimal places.\n\n"
    "The subtle pair is p3m1 and p31m. Both have three-fold rotation and "
    "three mirrors, and they are genuinely different groups: in p3m1 all "
    "three rotation centres of the cell sit on mirror lines, in p31m only "
    "one does. Getting that wrong gives you two copies of the same pattern "
    "and a list of sixteen.\n\n"
    "In three dimensions the same question has 230 answers instead of 17, "
    "which is why crystallographers have a thicker book."
)

TAGS_EXTRA = [
    "wallpaper groups", "symmetry", "group theory", "crystallography",
    "tessellation", "tiling", "escher", "alhambra", "plane symmetry",
    "fedorov", "pattern", "geometry",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    return BODY_TMPL.format(total=ev["total"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_wallpaper_short.py")

    description = build_description(
        body(), hashtags=["#symmetry", "#grouptheory", "#tessellation", "#patterns"]
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
