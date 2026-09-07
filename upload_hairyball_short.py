"""Sube el short 'Bola peluda' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para las 08:00 hora de Chile del dia siguiente.

    python upload_hairyball_short.py
    python upload_hairyball_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_hairyball", "shorts_hairyball_branded.mp4")

# Chile: UTC-4 en invierno (abr-sep), UTC-3 en verano (sep-abr).
CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Somewhere on Earth the Wind Is Always Zero 🌍 #math #shorts"

BODY = (
    "Right now, somewhere on this planet, there is a spot where the horizontal "
    "wind is exactly zero. Not almost. Exactly. And there is no weather pattern "
    "that can get rid of it.\n\n"
    "This is the hairy ball theorem, and it is not about weather at all — it is "
    "about spheres. Comb a sphere covered in hair and you cannot make every "
    "hair lie flat. Somewhere a cowlick has to form. Try any pattern you like; "
    "a bald spot or a swirl always appears.\n\n"
    "Here 22,000 flow lines are combed across a sphere. Watch the poles: every "
    "line spirals in and the speed drops to nothing. Gold marks slow, cyan "
    "marks fast. Those two still points are the cowlicks, and they cannot be "
    "removed — only moved around or merged.\n\n"
    "The reason is topology, not fluid dynamics. Poincaré and Hopf proved that "
    "the indices of the zeros of any tangent field must add up to the Euler "
    "characteristic of the surface, and for a sphere that number is 2. It is "
    "not zero, so the zeros cannot all cancel out.\n\n"
    "A doughnut has Euler characteristic 0. You can comb a doughnut perfectly. "
    "The atmosphere is just unlucky about its shape."
)

TAGS_EXTRA = [
    "hairy ball theorem", "vector field", "topology", "poincare hopf",
    "euler characteristic", "sphere", "wind", "no wind", "differential topology",
    "flow field", "streamlines", "mathematics", "geometry", "counterintuitive",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_hairyball_short.py")

    description = build_description(
        BODY, hashtags=["#topology", "#vectorfield", "#wind", "#hairyball"]
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
