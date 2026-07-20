"""Sube el short 'Solitones KdV' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para el jueves 2026-07-23 08:00 hora de Chile
(UTC-4 en julio) = 12:00 UTC.

    python upload_soliton_short.py
    python upload_soliton_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_soliton", "shorts_soliton_branded.mp4")

CHILE_UTC_OFFSET = -4
DEFAULT_LOCAL = datetime(2026, 7, 23, 8, 0, 0)

TITLE = "Waves That Pass Through Each Other: The 1834 Soliton 🌊✨ #math #shorts"

BODY = (
    "In 1834 the engineer John Scott Russell watched a single wave break away "
    "from a boat in a canal, keep its exact shape, and roll on for almost two "
    "miles. He chased it on horseback. Nobody could explain it for 60 years.\n\n"
    "It was a soliton. The Korteweg-de Vries equation finally described it: a "
    "wave so perfectly balanced between spreading and steepening that it never "
    "breaks. What you see here is a space-time view of three solitons — taller "
    "means faster — passing straight through each other and re-emerging with the "
    "same shape and speed. That pass-through is what makes a wave a soliton."
)

TAGS_EXTRA = [
    "soliton", "solitary wave", "kdv equation", "korteweg-de vries",
    "john scott russell", "wave physics", "nonlinear waves", "fluid dynamics",
    "space time diagram", "wave collision",
]


def _default_publish_at() -> str:
    utc = DEFAULT_LOCAL - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}")

    description = build_description(
        BODY, hashtags=["#soliton", "#waves", "#physics", "#KdV"]
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
        print(f"Se publica : {publish_at}  (= jueves 2026-07-23 08:00 Chile)")

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
