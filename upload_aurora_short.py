"""Sube el short 'Aurora sobre el lago' (15s, 1080x1920) PROGRAMADO.

    python upload_aurora_short.py
    python upload_aurora_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_aurora", "shorts_aurora.mp4")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "The Sky Is Not Painted, It Is Solved 🌌 Aurora Over a Lake #shorts"

BODY = (
    "Six curtains of light, and not one of them was drawn. Each is a curve "
    "whose axis drifts as it climbs, with the glow falling off by distance "
    "from that axis — so the shape you see is what the equation does, not what "
    "a brush did.\n\n"
    "The vertical streaks are the part that is really happening up there. In a "
    "real aurora, charged particles from the sun spiral down along the Earth's "
    "magnetic field lines and strike the upper atmosphere. The field lines run "
    "roughly vertical near the poles, which is why the light hangs in ribbons "
    "instead of pooling into clouds. Green is oxygen at about 100 km. The "
    "violet at the top is nitrogen, higher up.\n\n"
    "The lake is the sky itself, sampled again — flipped, compressed, and "
    "pushed sideways by a wave. That horizontal shove is the whole reason it "
    "reads as water.\n\n"
    "Every motion is built from waves that complete a whole number of cycles "
    "in fifteen seconds — the curtains, the streaks, the star twinkle, the "
    "ripples. So it loops with no seam and no cut. The music is generated the "
    "same way: a D minor ninth chord with bells on a pentatonic scale.\n\n"
    "Made entirely in Python. No 3D, no footage, no assets, no samples."
)

TAGS_EXTRA = [
    "aurora", "northern lights", "aurora borealis", "generative art",
    "procedural art", "night sky", "lake", "reflection", "relaxing",
    "ambient", "cozy", "creative coding", "python art", "aesthetic",
    "generative music", "ambient music", "procedural audio",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_aurora_short.py")

    description = build_description(
        BODY, hashtags=["#aurora", "#northernlights", "#generativeart", "#creativecoding"]
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
        video_path=VIDEO, title=TITLE, description=description, tags=tags,
        privacy_status=privacy, desired_channel="MathRelaxing",
        publish_at=publish_at, progress_callback=on_progress,
    )
    print(f"\n\nSubido a '{channel_name}'")
    print(f"https://youtu.be/{video_id}")
    if publish_at:
        print(f"Programado: se hace publico solo el {publish_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
