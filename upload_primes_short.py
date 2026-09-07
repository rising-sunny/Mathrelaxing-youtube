"""Sube el short 'Espiral de primos' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para las 08:00 hora de Chile del dia siguiente.

    python upload_primes_short.py
    python upload_primes_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_primes", "shorts_primes_branded.mp4")

# Chile: UTC-4 en invierno (abr-sep), UTC-3 en verano (sep-abr).
CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "One Formula, 40 Primes in a Row 🌀 The Prime Spiral #math #shorts"

BODY = (
    "Put every whole number on a spiral — distance √n from the centre, angle "
    "2π√n — and something strange happens. The primes refuse to scatter. They "
    "fall onto curved rays, and nobody has a full explanation for the pattern "
    "you are looking at.\n\n"
    "The bright cyan arc is the most famous of those rays: Euler's polynomial, "
    "n² + n + 41. Feed it n = 0, 1, 2, 3… and it returns a prime every single "
    "time for forty numbers straight — 41, 43, 47, 53, 61, 71, 83… all the way "
    "to 1601. Then it breaks at n = 40, which gives 41 × 41.\n\n"
    "No polynomial can produce primes forever; that much is proven. But why "
    "some of them stay lucky for so long, and why they carve these particular "
    "arcs into the spiral, runs straight into the deepest open questions in "
    "number theory.\n\n"
    "Gold points are primes. The faint blue dust is everything else — and there "
    "is far more of it. 150,000 numbers here, 13,848 of them prime."
)

TAGS_EXTRA = [
    "prime numbers", "prime spiral", "sacks spiral", "ulam spiral",
    "euler polynomial", "number theory", "primes", "riemann hypothesis",
    "mathematics", "prime pattern", "sieve of eratosthenes", "integers",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_primes_short.py")

    description = build_description(
        BODY, hashtags=["#primes", "#numbertheory", "#euler", "#primespiral"]
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
