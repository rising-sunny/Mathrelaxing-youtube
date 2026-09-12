"""Sube el short 'DLA' (15s, 1080x1920) PROGRAMADO.

    python upload_dla_short.py
    python upload_dla_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_dla", "shorts_dla_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_dla_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "One Rule, Pure Chance, and Nobody Can Predict It 🌿 #math #shorts"

BODY_TMPL = (
    "A particle starts far away and wanders at random. If it touches the "
    "cluster, it freezes there forever and the next one starts. That is the "
    "whole rule. No forces, no equation of motion — just a random walk and a "
    "contact condition.\n\n"
    "Out of those two lines comes something that is not random at all. The "
    "mass inside a radius r follows a power law:\n\n"
    "N(r) ∝ r^D\n\n"
    "On the cluster you just watched grow, fitted over a decade of radii, "
    "D = {dim:.2f} with R² = {r2:.4f}. For infinitely large clusters the "
    "accepted value is about 1.71 — and after forty-plus years there is "
    "still no derivation of it. It is measured, not deduced. Finite clusters "
    "like this one come out a little under the asymptotic value.\n\n"
    "Why it branches: a tip that sticks out intercepts wandering particles "
    "before they can reach the bottom of a gap, so it grows faster and sticks "
    "out more. The advantage compounds. That runaway is the Mullins–Sekerka "
    "instability, the same one behind snowflakes, frost on a window, mineral "
    "dendrites and copper growing on an electrode.\n\n"
    "Witten and Sander wrote the model down in 1981. Colour here runs from "
    "the first particles that stuck to the last ones, so what you see is the "
    "growth history, frozen."
)

TAGS_EXTRA = [
    "diffusion limited aggregation", "dla", "fractal dimension",
    "random walk", "brownian motion", "probability", "fractal growth",
    "witten sander", "dendrite", "mullins sekerka", "self similarity",
    "stochastic process", "power law", "emergence",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    return BODY_TMPL.format(dim=ev["dimension"], r2=ev["fit_r2"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_dla_short.py")

    description = build_description(
        body(), hashtags=["#fractal", "#probability", "#randomwalk", "#dla"]
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
