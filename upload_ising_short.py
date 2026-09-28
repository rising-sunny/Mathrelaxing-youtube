"""Sube el short 'Iman de Ising' (15s, 1080x1920) PROGRAMADO.

    python upload_ising_short.py
    python upload_ising_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_ising",
                     "shorts_ising_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_ising_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Half a Million Magnets Find Order 🧲 #physics #shorts"

BODY_TMPL = (
    "Every tiny square on screen is a magnet, a spin, pointing up (blue) "
    "or down (orange). {nsp:,} of them. Each one wants to point the same way "
    "as its four neighbours. Heat shakes them at random. That tug of war is "
    "the Ising model:\n\n"
    "H = -J sum s_i s_j - h sum s_i\n\n"
    "HOT: noise. The heat wins and there is no pattern at all.\n\n"
    "At exactly T = 2.269 something strange happens: clusters appear at "
    "every size at once, islands inside lakes inside islands. That is the "
    "critical point, and its temperature is known exactly: Lars Onsager "
    "solved the 2-D Ising model by hand in 1944, Tc = 2 / ln(1 + sqrt 2).\n\n"
    "COLD: order wins. Domains grow and swallow each other until the whole "
    "magnet points one way. Nobody told it which way.\n\n"
    "Then a magnetic field pushes AGAINST it. Nothing happens, until tiny "
    "islands of the other colour pop up by chance and grow. They are square "
    "because at low temperature the grid itself shapes them. The magnet "
    "flips in an avalanche.\n\n"
    "This is a Monte Carlo simulation (Metropolis, checkerboard updates) run "
    "with Taichi. Onsager's exact result also gives the magnetisation below "
    "Tc, M = (1 - sinh(2/T)^-4)^(1/8), and the simulation was checked "
    "against it before anything was drawn: {rows}. Above Tc it measured "
    "{mhot:.3f}, where the exact answer is zero."
)

TAGS_EXTRA = [
    "ising model", "phase transition", "critical point", "onsager",
    "statistical mechanics", "ferromagnet", "monte carlo", "metropolis",
    "fractal", "emergence", "magnetism", "taichi",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    rows = ev["verify"]["rows"]
    txt = ", ".join(f"at T = {T} it measured M = {m:.4f} against {o:.4f}"
                    for T, m, o in rows[:3])
    return BODY_TMPL.format(nsp=(ev["w"] // 3) * (ev["h"] // 3), rows=txt,
                            mhot=rows[3][1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_ising_short.py")

    description = build_description(
        body(), hashtags=["#physics", "#magnetism", "#fractal", "#science"]
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
