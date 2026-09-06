"""Sube el short 'Pila de arena abeliana' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para las 08:00 hora de Chile del dia siguiente.

    python upload_sandpile_short.py
    python upload_sandpile_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_sandpile", "shorts_sandpile_branded.mp4")

# Chile: UTC-4 en invierno (abr-sep), UTC-3 en verano (sep-abr).
CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "500,000 Grains of Sand, One Rule 🏜️ The Abelian Sandpile #math #shorts"

BODY = (
    "Drop half a million grains of sand on a single square. One rule: any square "
    "holding 4 or more grains topples, handing one grain to each of its four "
    "neighbours. Repeat until nobody has 4.\n\n"
    "What falls out is not a heap. It is this fractal — and it is the only one "
    "possible. Deepak Dhar proved in 1990 that the final pattern does not depend "
    "on the order you let the squares topple in; scramble the sequence however "
    "you like and you land on the exact same image. That is the 'abelian' in "
    "abelian sandpile.\n\n"
    "Bak, Tang and Wiesenfeld introduced the model in 1987 as the cleanest "
    "example of self-organized criticality: a system that tunes itself to the "
    "edge of chaos with nobody adjusting anything. Every grain here is placed by "
    "the same rule a child could follow, and nobody has fully explained why the "
    "limit shape looks like this."
)

TAGS_EXTRA = [
    "abelian sandpile", "sandpile model", "self-organized criticality",
    "cellular automaton", "bak tang wiesenfeld", "deepak dhar", "fractal",
    "emergence", "discrete math", "chaos", "sand", "mathematical art",
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
        sys.exit(f"No existe el video: {VIDEO}\n"
                 "  python build_sandpile_short.py\n"
                 "  python tools/brand_cta.py -i output/shorts_sandpile/shorts_sandpile.mp4")

    description = build_description(
        BODY, hashtags=["#sandpile", "#fractal", "#emergence", "#cellularautomata"]
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
