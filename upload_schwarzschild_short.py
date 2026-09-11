"""Sube el short 'Schwarzschild' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para las 08:00 hora de Chile del dia siguiente.

    python upload_schwarzschild_short.py
    python upload_schwarzschild_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_schwarzschild",
                     "shorts_schwarzschild_branded.mp4")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Newton Says These Orbits Close. They Don't 🕳️ Black Hole #math #shorts"

BODY = (
    "Every streak is one particle on a geodesic — the straightest possible "
    "path through curved spacetime. Around a black hole the radial equation "
    "for that path is:\n\n"
    "d²r/dτ² = −M/r² + L²/r³ − 3ML²/r⁴\n\n"
    "The first two terms are exactly Newton: gravity pulling in, centrifugal "
    "effect pushing out. Those two alone give a closed ellipse that repeats "
    "forever.\n\n"
    "The third term does not exist in Newton. It comes from the curvature of "
    "spacetime itself, and it is why nothing here ever traces the same path "
    "twice. Each lap the closest approach shifts a little, and the orbit "
    "sweeps out a rosette. Around the Sun that same term moves Mercury's "
    "perihelion by 43 arcseconds per century — the first thing general "
    "relativity ever got right that Newton got wrong.\n\n"
    "It also creates two radii Newton has no idea about. The gold ring is "
    "r = 6M, the innermost stable circular orbit: closer in than that, no "
    "stable orbit exists at all. The pale ring is r = 3M, the photon sphere, "
    "where light itself can orbit. Cross inward past it and you are captured "
    "— the peak of the effective potential never sits below 3M, so there is "
    "nothing left to turn you around.\n\n"
    "Integrated in the coordinate time of a distant observer, which is why "
    "nothing is ever seen to cross the horizon: the infalling particles slow "
    "to a stop at the rim and fade out, dimmed by their own gravitational "
    "redshift."
)

TAGS_EXTRA = [
    "black hole", "general relativity", "schwarzschild", "geodesic",
    "event horizon", "photon sphere", "isco", "spacetime curvature",
    "perihelion precession", "mercury precession", "einstein",
    "gravitational redshift", "orbital mechanics", "astrophysics",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_schwarzschild_short.py")

    description = build_description(
        BODY, hashtags=["#blackhole", "#relativity", "#physics", "#spacetime"]
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
