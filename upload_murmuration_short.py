"""Sube el short 'Murmuracion' (15s, 1080x1920) PROGRAMADO.

    python upload_murmuration_short.py
    python upload_murmuration_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_murmur",
                     "shorts_murmur_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_murmur_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "30,000 Birds. No Leader. Just One Rule 🐦 #math #shorts"

BODY_TMPL = (
    "Nobody is in charge of a murmuration. There is no leader and no plan. "
    "Every starling looks at its 7 nearest neighbours, and only those 7, "
    "and tries to fly the way they fly.\n\n"
    "That single local rule is enough for {n:,} birds to move like one "
    "liquid body.\n\n"
    "What you are watching is a simulation of exactly that. Each bird "
    "aligns with its 7 nearest neighbours (the number measured in real "
    "starling flocks in Rome), keeps close to the birds around it without "
    "colliding, and prefers to fly level with them, which is why the flock "
    "becomes a thin sheet. Where the sheet turns edge-on to you, it looks "
    "dark. That is where those ripples of shadow come from.\n\n"
    "The number on screen, phi, is the order parameter: the length of the "
    "average flight direction. 0 means every bird flies its own way, 1 means "
    "all of them fly the same way. It starts at {p0:.2f}, pure chaos, and "
    "climbs to {pmax:.2f} with nobody giving an order.\n\n"
    "Then a falcon dives through, twice. The birds near it swerve, their "
    "neighbours copy the swerve, and the panic travels through the flock as "
    "a wave. Order drops to {pmin:.2f}, the "
    "sheet tears and folds, and then it heals itself. At dusk the flock "
    "pours down into the reeds to sleep.\n\n"
    "The maths underneath was checked first. In the Vicsek model, the "
    "simplest version of this rule, order must switch off as noise goes "
    "up, like a magnet losing its magnetism when heated. Measured with 2,500 "
    "particles: phi = {v0:.2f} with little noise, {v1:.2f}, {v2:.2f}, and "
    "{v3:.2f} with a lot of it. A phase transition, out of nothing but "
    "neighbours copying neighbours."
)

TAGS_EXTRA = [
    "murmuration", "starlings", "flocking", "emergence", "collective behaviour",
    "vicsek model", "boids", "complex systems", "self organization",
    "phase transition", "swarm intelligence", "nature math",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    phis = [s["phi"] for s in ev["shown"]]
    f0 = int(ev["t_falcon"][0] * ev["fps"])
    f1 = int(ev["t_roost"] * ev["fps"])
    v = ev["verify"]["phis"]
    return BODY_TMPL.format(
        n=ev["n"], p0=phis[0], pmax=max(phis[:f0]), pmin=min(phis[f0:f1]),
        v0=v[0], v1=v[1], v2=v[2], v3=v[3])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_murmuration_short.py")

    description = build_description(
        body(), hashtags=["#nature", "#emergence", "#starlings", "#science"]
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
