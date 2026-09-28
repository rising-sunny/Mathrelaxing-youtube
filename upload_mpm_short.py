"""Sube el short 'Cuatro materiales' (15s, 1080x1920) PROGRAMADO.

    python upload_mpm_short.py
    python upload_mpm_short.py --now      # unlisted ya, sin programar
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_mpm",
                     "shorts_mpm_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_mpm_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Jelly, Snow, Sand, Water: One Equation 🧪 #physics #shorts"

BODY_TMPL = (
    "Four materials that could not behave more differently, and every one "
    "of them obeys the same law, conservation of momentum:\n\n"
    "rho Dv/Dt = div(sigma) + rho g\n\n"
    "The only thing that changes is sigma, the stress: how the material "
    "answers when it is deformed.\n\n"
    "The JELLY is elastic. Squash it and the stress pushes it back. The grid "
    "painted on it is drawn in its resting shape, so you can watch it bend "
    "and spring back.\n\n"
    "The SNOW is the same elastic law with a breaking point. Once it is "
    "stretched past a limit the deformation becomes permanent, and it "
    "cracks. This is the model Disney used for the snow in Frozen.\n\n"
    "The SAND is held together by nothing but friction, the Drucker-Prager "
    "law. It can hold a gentle slope but not a steep one, and it never "
    "sticks to itself.\n\n"
    "The WATER has only pressure. No shape at all.\n\n"
    "At the end the box tilts. Gravity turns, and all four answer to the "
    "same g in their own way.\n\n"
    "This is the Material Point Method, {n:,} particles carrying the "
    "material through a grid where the equation is solved, simulated with "
    "Taichi. Checked before a single frame was drawn: the particles hand "
    "their mass to the grid to {me:.0e}; a falling block accelerates at "
    "exactly g, to {ge:.0e}; and a wedge of sand at {w0:.0f} degrees stays "
    "put ({w0e:.1f}) while wedges at {w1:.0f} and {w2:.0f} degrees collapse "
    "to {w1e:.0f} and {w2e:.0f}."
)

TAGS_EXTRA = [
    "material point method", "mpm", "physics simulation", "continuum mechanics",
    "taichi", "jelly", "snow simulation", "sand", "fluid simulation",
    "drucker prager", "frozen snow", "satisfying physics",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    v = ev["verify"]
    ws, we = v["wedges"]["start"], v["wedges"]["end"]
    return BODY_TMPL.format(n=ev["n"], me=v["mass_err"], ge=v["g_err"],
                            w0=ws[0], w1=ws[1], w2=ws[2],
                            w0e=we[0], w1e=we[1], w2e=we[2])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_mpm_short.py")

    description = build_description(
        body(), hashtags=["#physics", "#simulation", "#satisfying", "#science"]
    )
    tags = build_tags(TAGS_EXTRA)

    if a.now:
        publish_at, privacy = None, "unlisted"
    else:
        publish_at = a.publish_at or _default_publish_at()
        privacy = "private"

    print(f"Video      : {os.path.basename(VIDEO)} "
          f"({os.path.getsize(VIDEO) / (1024 * 1024):.1f} MB)")
    print(f"Titulo     : {TITLE}")
    print(f"Privacidad : {privacy}")

    def on_progress(p):
        sys.stdout.write(f"\rSubiendo... {p}%")
        sys.stdout.flush()

    video_id, channel_name = upload_video_to_youtube(
        video_path=VIDEO, title=TITLE, description=description, tags=tags,
        privacy_status=privacy, desired_channel="MathRelaxing",
        publish_at=publish_at, progress_callback=on_progress,
    )
    print(f"\n\nSubido a '{channel_name}'")
    print(f"https://youtu.be/{video_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
