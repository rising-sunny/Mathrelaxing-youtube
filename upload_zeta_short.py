"""Sube el short 'Zeta' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para las 08:00 hora de Chile del dia siguiente.

    python upload_zeta_short.py
    python upload_zeta_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_zeta", "shorts_zeta_branded.mp4")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Every Zero Lands on the Same Line 🎯 Riemann Hypothesis #math #shorts"

BODY = (
    "Every pixel here is a complex number s, and the color is the direction "
    "the zeta function points there. Where the colors spin all the way "
    "around a single point, zeta is zero.\n\n"
    "Watch where those points fall. Not scattered. Every one of them sits "
    "exactly on the vertical gold line, Re(s) = 1/2.\n\n"
    "Zeta starts as a simple sum, and Euler found it is also a product over "
    "the prime numbers:\n\n"
    "ζ(s) = 1 + 1/2ˢ + 1/3ˢ + ... = ∏ₚ 1/(1 − p⁻ˢ)\n\n"
    "That identity is why the zeros matter: they control how the primes are "
    "spread out among the integers. If they all really are on that line, the "
    "primes are as evenly distributed as they could possibly be.\n\n"
    "The first ten trillion zeros have been checked. All on the line. Riemann "
    "guessed it in 1859 and nobody has proved it since — it is one of the "
    "seven Millennium Prize Problems, worth a million dollars.\n\n"
    "The sum only converges when Re(s) > 1, so the plane you are looking at "
    "is the analytic continuation, computed here with Euler–Maclaurin."
)

TAGS_EXTRA = [
    "riemann hypothesis", "riemann zeta function", "zeta function",
    "prime numbers", "number theory", "domain coloring", "complex analysis",
    "millennium prize problem", "critical line", "analytic continuation",
    "euler product", "unsolved problems", "mathematics",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_zeta_short.py")

    description = build_description(
        BODY, hashtags=["#riemann", "#primes", "#numbertheory", "#zeta"]
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
        print(f"Programado: se hace publico el {publish_at}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
