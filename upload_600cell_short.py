"""Sube el short '600-cell' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para las 08:00 hora de Chile del dia siguiente.

    python upload_600cell_short.py
    python upload_600cell_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_600cell", "shorts_600cell_branded.mp4")

# Chile: UTC-4 en invierno (abr-sep), UTC-3 en verano (sep-abr).
CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "600 Tetrahedra in 4 Dimensions 🔷 The 600-Cell #math #shorts"

BODY = (
    "In three dimensions there are exactly five Platonic solids. In four "
    "dimensions there are six — and this is the one with no counterpart down "
    "here: 600 regular tetrahedra glued face to face, closing up perfectly "
    "with 120 corners and 720 edges.\n\n"
    "It cannot be built in our space, so you are seeing its shadow. Every "
    "corner sits on the 3-sphere and is projected down by the same trick that "
    "flattens a globe onto a map. That projection is what bends the straight "
    "edges into arcs: none of these curves are curved in 4D.\n\n"
    "The rotation is isoclinic — the same angle in two perpendicular planes at "
    "once, something only four dimensions allow. Every point travels along a "
    "Hopf fibre, and after a full turn the shape lands exactly on itself, so "
    "this loops seamlessly. Colour marks the fourth coordinate: blue is far "
    "from the projection pole, gold is close to it.\n\n"
    "Schläfli symbol {3,3,5}. Catalogued by Ludwig Schläfli in the 1850s, "
    "decades before anyone could draw it."
)

TAGS_EXTRA = [
    "600-cell", "4d geometry", "four dimensions", "polytope", "regular polytope",
    "platonic solid", "hypersphere", "stereographic projection", "hopf fibration",
    "schlafli", "geometry", "4d rotation", "tesseract", "hyperdimensional",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_600cell_short.py")

    description = build_description(
        BODY, hashtags=["#4D", "#geometry", "#polytope", "#hopffibration"]
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
