"""Sube el short 'Cat map' (15s, 1080x1920) PROGRAMADO.

    python upload_catmap_short.py
    python upload_catmap_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_catmap", "shorts_catmap_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_catmap_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "This Image Is Destroyed. Then It Comes Back Exactly. 🐈‍⬛ #math #shorts"

BODY_TMPL = (
    "One line does all of it. Take an image of {n} by {n} pixels and send "
    "every pixel to a new place:\n\n"
    "(x, y) → (2x + y, x + y)  mod {n}\n\n"
    "That matrix has determinant 1, so nothing is created and nothing is "
    "lost — it is a pure shuffle of the pixels that were already there. Its "
    "eigenvalues are (3 ± √5)/2, which is φ² ≈ 2.618 and its reciprocal: "
    "every step stretches the picture by the golden ratio squared in one "
    "direction and squeezes it by the same amount in the other, then wraps it "
    "around the torus. Ten steps in, there is nothing left to recognise.\n\n"
    "Here is what almost nobody expects. A shuffle of a finite set has finite "
    "order. Keep applying it and the picture has to come back. Not something "
    "similar — the same picture, pixel for pixel. For {n} it takes exactly "
    "{period} steps. Measured here against the original: {diff} levels of "
    "difference out of 255.\n\n"
    "The period is wildly erratic in the image size and there is no known "
    "closed form for it. {n} gives {period}. 127 gives 128. 124 gives 15.\n\n"
    "Vladimir Arnold demonstrated this in the 1960s using a picture of a cat, "
    "which is why it has the name it has. Nothing here is edited or reversed: "
    "the clip runs forward the whole way."
)

TAGS_EXTRA = [
    "arnold cat map", "poincare recurrence", "ergodic theory", "chaos",
    "golden ratio", "linear algebra", "modular arithmetic", "torus",
    "dynamical systems", "permutation", "eigenvalues", "mixing",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    return BODY_TMPL.format(n=ev["n"], period=ev["period"], diff=ev["max_diff"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_catmap_short.py")

    description = build_description(
        body(), hashtags=["#chaos", "#goldenratio", "#linearalgebra", "#recurrence"]
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
