"""Sube el short 'Three-Body Figure-8' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para el martes 2026-07-21 08:00 hora de Chile
(UTC-4 en julio) = 12:00 UTC.

    python upload_threebody_short.py
    python upload_threebody_short.py --publish-at 2026-07-21T13:00:00Z
    python upload_threebody_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_threebody", "shorts_threebody_branded.mp4")

CHILE_UTC_OFFSET = -4  # julio = horario estandar en Chile
DEFAULT_LOCAL = datetime(2026, 7, 21, 8, 0, 0)

TITLE = "The Three-Body Problem's Perfect Orbit: 3 Bodies, 1 Path 🌀✨ #math #shorts"

BODY = (
    "Three masses pulling on each other is chaos — no general formula predicts "
    "where they end up. Yet this orbit exists: three equal bodies chasing each "
    "other along one single shared figure-8 curve, repeating forever.\n\n"
    "Cristopher Moore found it numerically in 1993; Chenciner and Montgomery "
    "proved it really exists in 2000. It is one of the very few stable periodic "
    "solutions known to a problem that is otherwise unpredictable."
)

TAGS_EXTRA = [
    "three body problem", "3 body problem", "figure eight orbit", "celestial mechanics",
    "orbital mechanics", "n-body", "chaos theory", "gravity", "astronomy",
    "cristopher moore", "periodic orbit", "numpy",
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
        sys.exit(f"No existe el video: {VIDEO}\n"
                 "Genera primero: python build_threebody_short.py "
                 "&& python tools/brand_cta.py -i output/shorts_threebody/shorts_threebody.mp4 "
                 "-o output/shorts_threebody/shorts_threebody_branded.mp4")

    description = build_description(
        BODY, hashtags=["#ThreeBodyProblem", "#chaos", "#orbit", "#physics"]
    )
    tags = build_tags(TAGS_EXTRA)

    if a.now:
        publish_at, privacy = None, "unlisted"
    else:
        publish_at = a.publish_at or _default_publish_at()
        privacy = "private"  # YouTube lo exige cuando hay publishAt

    size_mb = os.path.getsize(VIDEO) / (1024 * 1024)
    print(f"Video      : {os.path.basename(VIDEO)} ({size_mb:.1f} MB)")
    print(f"Titulo     : {TITLE}")
    print(f"Privacidad : {privacy}")
    if publish_at:
        print(f"Se publica : {publish_at}  (= martes 2026-07-21 08:00 Chile)")

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
