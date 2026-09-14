"""Sube el short 'Tautocrona' (15s, 1080x1920) PROGRAMADO.

    python upload_tauto_short.py
    python upload_tauto_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_tauto", "shorts_tauto_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_tauto_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Dropped From Different Heights. They Land Together. ⏱️ #math #shorts"

BODY_TMPL = (
    "Two bowls, the same depth and the same width, drawn inside the same box "
    "so you can check. The top one is an arc of a circle. The bottom one is a "
    "cycloid — the curve a point on a rolling wheel traces out.\n\n"
    "Six beads, six different starting heights, all released at the same "
    "instant. On the circle they drift apart: a pendulum's period grows with "
    "its swing, so the high ones fall behind. By the end of this clip they "
    "reach the bottom {gap:.2f} seconds apart.\n\n"
    "On the cycloid they never drift. Not approximately: the gap measured "
    "across all {ncross} passes through the bottom is exactly zero. The "
    "cycloid needs no numerical integration at all — the motion has a closed "
    "form, so there is no error to accumulate.\n\n"
    "The reason is one line of algebra. Measure the arc σ travelled from the "
    "lowest point of a cycloid and the height above that point turns out to "
    "be exactly\n\n"
    "h = σ² / 8r\n\n"
    "Height is a perfect quadratic in distance travelled. That is the "
    "definition of a harmonic oscillator, so σ'' = −(g/4r)·σ and the period "
    "is T = 4π√(r/g) — with no amplitude in it anywhere. A circle only "
    "approximates that near the bottom, which is why pendulum clocks lose "
    "time as they wind down.\n\n"
    "Christiaan Huygens found this in 1659 and built a clock with cycloidal "
    "cheeks to force the bob onto exactly this curve. The same cycloid is "
    "also the brachistochrone, the fastest slide between two points. One "
    "curve, both records.\n\n"
    "The cycloid bowl completes exactly four swings in these 15 seconds, so "
    "it loops seamlessly. The circular one cannot: its period depends on "
    "where you start."
)

TAGS_EXTRA = [
    "tautochrone", "brachistochrone", "cycloid", "huygens", "pendulum",
    "calculus of variations", "simple harmonic motion", "isochronous",
    "physics", "classical mechanics", "period", "clock",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    gap = max(s[0] for s in ev["spreads"])
    return BODY_TMPL.format(gap=gap, ncross=ev["crossings"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_tauto_short.py")

    description = build_description(
        body(), hashtags=["#physics", "#cycloid", "#pendulum", "#huygens"]
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
