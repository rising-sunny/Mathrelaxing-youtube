"""Sube el short 'Every Note Has a Shape' (Chladni mandala, 15s).

Usa el video CON la marca quemada (shorts_mandala_branded.mp4): es el primer
short del canal que pide la suscripcion en pantalla.

    python upload_mandala_notes.py              # unlisted (default, para revisar)
    python upload_mandala_notes.py --public
"""

import argparse
import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_mandala", "shorts_mandala_branded.mp4")

TITLE = "Every Note Has a Shape: 300,000 Grains of Sand 🌀✨ #math #physics #shorts"

BODY = (
    "A Chladni plate turns sound into geometry: as the driving frequency changes, "
    "300,000 grains flee the vibrating zones and settle exactly on the nodal lines "
    "where the plate stays still.\n\n"
    "Every note carries its own shape. The pattern you see is the standing wave made "
    "visible — simulated grain by grain, then sonified so the audio you hear drives "
    "the geometry you watch."
)

TAGS_EXTRA = [
    "chladni", "cymatics", "standing waves", "nodal lines", "sound visualization",
    "sand patterns", "vibration", "acoustics", "resonance", "physics simulation",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", action="store_true",
                    help="Subir como publico (default: unlisted para revisar)")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}")

    privacy = "public" if a.public else "unlisted"
    description = build_description(
        BODY, hashtags=["#cymatics", "#Chladni", "#sound", "#physics"]
    )
    tags = build_tags(TAGS_EXTRA)

    size_mb = os.path.getsize(VIDEO) / (1024 * 1024)
    print(f"Video   : {os.path.basename(VIDEO)} ({size_mb:.1f} MB)")
    print(f"Titulo  : {TITLE}")
    print(f"Privacy : {privacy}")

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
        progress_callback=on_progress,
    )
    print(f"\n\nSubido a '{channel_name}' como {privacy.upper()}")
    print(f"https://youtu.be/{video_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
