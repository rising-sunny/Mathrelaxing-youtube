"""Sube el short 'Fold' (15s, 1080x1920) PROGRAMADO.

    python upload_fold_short.py
    python upload_fold_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_fold", "shorts_fold_branded.mp4")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Four Lines of Algebra. No Simulation at All. 🎏 #math #shorts"

BODY = (
    "There is no physics here. Nothing is being integrated, nothing has a "
    "velocity, no point knows about any other point. Every one of the 378,000 "
    "dots is a pair of numbers (x, y) from a flat grid, pushed through four "
    "lines of algebra and dropped on the screen:\n\n"
    "a = 7.2y     s = sin(50x)·cos(6.8y)\n"
    "r = 20 + 46y + 15·sin(2.6a − 6πτ) + 12s\n"
    "c = a + 0.55·sin(1.4a − 2πτ) + 0.3s − 2πτ\n"
    "(u, v) = (r·sin c, (r + 10s)·cos c)\n\n"
    "The trick that makes the fine combing is that the two directions of the "
    "grid do completely different jobs. The slow one sweeps the angle and "
    "draws the arc; the fast one adds a high-frequency wobble that stacks "
    "curves almost on top of each other. Let both of them move at the same "
    "rate and you get a solid blob instead.\n\n"
    "It loops perfectly, and not by editing: τ runs from 0 to 1 across the "
    "clip and every term with τ in it is 2π times a whole number, so the last "
    "frame lands exactly on the first. Measured difference between them: "
    "1 part in 10 trillion.\n\n"
    "Written from scratch for this channel. The technique of folding a sheet "
    "of points with one long expression is public and widely documented; the "
    "expression above is ours."
)

TAGS_EXTRA = [
    "generative art", "parametric equations", "point cloud", "creative coding",
    "procedural art", "seamless loop", "trigonometry", "algebra",
    "parametric surface", "mathematical art", "algorithmic art", "processing",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_fold_short.py")

    description = build_description(
        BODY, hashtags=["#generativeart", "#creativecoding", "#parametric", "#loop"]
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
