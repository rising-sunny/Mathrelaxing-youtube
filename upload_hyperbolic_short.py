"""Sube el short 'Teselado hiperbolico' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para las 08:00 hora de Chile del dia siguiente.

    python upload_hyperbolic_short.py
    python upload_hyperbolic_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_hyperbolic", "shorts_hyperbolic_branded.mp4")

# Chile: UTC-4 en invierno (abr-sep), UTC-3 en verano (sep-abr).
CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Every Triangle Here Is the Same Size 🌀 Hyperbolic Geometry #math #shorts"

BODY = (
    "Look at the rim. Those slivers are not smaller than the triangles in the "
    "middle — they are exactly the same size. Every single one.\n\n"
    "This is the Poincaré disk, a flat map of a curved space, and like every "
    "flat map it lies about distance. Its ruler is ds = 2|dz| / (1 − |z|²): as "
    "you approach the edge the denominator collapses, so a step that looks "
    "microscopic on your screen is a full stride in the actual geometry. The "
    "boundary circle is infinitely far away. Nothing ever reaches it.\n\n"
    "Seven triangles meet at every corner here. On a flat sheet only six can — "
    "their angles would have to sum to less than 180°, which no flat triangle "
    "does. Hyperbolic space has room to spare, so it fits a seventh, and keeps "
    "fitting them forever.\n\n"
    "The motion is a hyperbolic rotation about a point off to one side. Watch "
    "how tiles stream out of the boundary, cross the disk, and vanish back into "
    "it. After one full turn the pattern lands exactly on itself, so this loops "
    "seamlessly.\n\n"
    "Escher spent years on this by hand, after Coxeter sent him a diagram."
)

TAGS_EXTRA = [
    "hyperbolic geometry", "poincare disk", "non-euclidean", "tessellation",
    "tiling", "escher", "coxeter", "curved space", "hyperbolic plane",
    "geometry", "infinity", "mathematical art", "circle limit",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_hyperbolic_short.py")

    description = build_description(
        BODY, hashtags=["#hyperbolic", "#geometry", "#escher", "#noneuclidean"]
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
