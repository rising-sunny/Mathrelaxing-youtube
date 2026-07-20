"""Sube el short 'Turing / Reaction-Diffusion' (15s) PROGRAMADO.

Programado por defecto para el 2026-07-20 08:00 hora de Chile (UTC-4 en julio,
Chile esta en horario estandar) = 12:00 UTC.

YouTube exige privacyStatus=private cuando se usa publishAt: el video queda
privado y se publica solo a la hora indicada.

    python upload_reaction_turing.py
    python upload_reaction_turing.py --publish-at 2026-07-20T13:00:00Z
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_reaction", "shorts_reaction_branded.mp4")

# Chile en julio = UTC-4 (horario estandar; el DST va de septiembre a abril)
CHILE_UTC_OFFSET = -4
DEFAULT_LOCAL = datetime(2026, 7, 20, 8, 0, 0)

TITLE = "Two Chemicals, 116,480 Cells: How Turing Explained Stripes 🌀✨ #math #shorts"

BODY = (
    "In 1952 Alan Turing asked how a featureless embryo decides where to put its "
    "stripes. His answer: two chemicals, one spreading faster than the other, "
    "reacting as they diffuse.\n\n"
    "That is the Gray-Scott model running here across 116,480 cells. Nothing "
    "tells the pattern where to go — the labyrinth emerges on its own from the "
    "feed and kill rates alone. The same math behind zebra stripes, leopard "
    "spots and coral growth."
)

TAGS_EXTRA = [
    "reaction diffusion", "turing pattern", "gray-scott", "alan turing",
    "morphogenesis", "emergence", "pattern formation", "chaos", "numpy",
    "cellular automata",
]


def _default_publish_at() -> str:
    utc = DEFAULT_LOCAL - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None,
                    help="ISO 8601 UTC, ej 2026-07-20T12:00:00Z")
    ap.add_argument("--now", action="store_true",
                    help="Subir unlisted ya, sin programar")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}")

    description = build_description(
        BODY, hashtags=["#TuringPattern", "#ReactionDiffusion", "#emergence", "#math"]
    )
    tags = build_tags(TAGS_EXTRA)

    if a.now:
        publish_at, privacy = None, "unlisted"
    else:
        publish_at = a.publish_at or _default_publish_at()
        # YouTube exige private cuando hay publishAt
        privacy = "private"

    size_mb = os.path.getsize(VIDEO) / (1024 * 1024)
    print(f"Video      : {os.path.basename(VIDEO)} ({size_mb:.1f} MB)")
    print(f"Titulo     : {TITLE}")
    print(f"Privacidad : {privacy}")
    if publish_at:
        print(f"Se publica : {publish_at}  (= 2026-07-20 08:00 Chile)")

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
