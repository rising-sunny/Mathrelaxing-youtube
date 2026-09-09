"""Sube el short 'Feigenbaum' (15s, 1080x1920) PROGRAMADO.

Programado por defecto para las 08:00 hora de Chile del dia siguiente.

    python upload_feigenbaum_short.py
    python upload_feigenbaum_short.py --now      # unlisted ya, sin programar
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from metadata import build_description, build_tags  # noqa: E402
from youtube_uploader import upload_video_to_youtube  # noqa: E402

VIDEO = os.path.join(REPO, "output", "shorts_feigenbaum", "shorts_feigenbaum_branded.mp4")

# Chile: UTC-4 en invierno (abr-sep), UTC-3 en verano (sep-abr).
CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "A Dripping Tap Hides This Number 🌀 4.669… #math #shorts"

BODY = (
    "Take the simplest equation that can misbehave: x → r·x·(1−x). It was "
    "written to model a population — rabbits that breed, then run out of food.\n\n"
    "Turn up r and watch. The population settles on one value. Then it splits "
    "and alternates between two. Then four. Then eight, sixteen, thirty-two — "
    "and the splits come faster and faster until, at r = 3.5699456…, there are "
    "infinitely many and the whole thing dissolves into chaos.\n\n"
    "Now measure the gaps between splits. Each one is about 4.669 times shorter "
    "than the one before. That ratio has a name, δ, and here is the strange "
    "part: it is not a property of this equation. Feigenbaum showed in 1978 "
    "that ANY equation with a single smooth hump does the same thing and gives "
    "the same 4.669. The formula does not matter.\n\n"
    "Which is why the number turns up in the lab. Physicists have measured "
    "period-doubling with Feigenbaum scaling in dripping taps, in convecting "
    "fluids, and in electronic oscillators — systems that share no equations "
    "with each other, only that shape.\n\n"
    "This zooms 4,751× toward the point where the splitting never ends."
)

TAGS_EXTRA = [
    "feigenbaum", "feigenbaum constant", "bifurcation diagram", "logistic map",
    "chaos theory", "period doubling", "universality", "nonlinear dynamics",
    "chaos", "dynamical systems", "attractor", "mathematics", "4.669",
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
        sys.exit(f"No existe el video: {VIDEO}\n  python build_feigenbaum_short.py")

    description = build_description(
        BODY, hashtags=["#chaos", "#feigenbaum", "#bifurcation", "#universality"]
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
