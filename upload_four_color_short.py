"""Sube el short 'Teorema de los cuatro colores' (15s, 1080x1920) PROGRAMADO.

    python upload_four_color_short.py
    python upload_four_color_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_four_color",
                     "shorts_four_color_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_four_color_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "It Took 124 Years To Prove You Only Need 4 Colours 🗺️ #math #shorts"

BODY_TMPL = (
    "In 1852 a student named Francis Guthrie, colouring a map of the "
    "counties of England, noticed he never needed more than four colours to "
    "keep neighbouring counties different. Is that true for every map ever "
    "drawn? It took until 1976 to prove it, and the proof was so long that a "
    "computer had to check it.\n\n"
    "This map has {n} countries, and it gets coloured live from the centre "
    "outwards. Most countries just take a colour none of their neighbours "
    "has. But sometimes a country is surrounded by all four. Then comes the "
    "clever move, from Alfred Kempe in 1879: pick two colours, say amber and "
    "teal, follow the chain of amber and teal countries connected to one "
    "neighbour, and swap them all. That frees up a colour. The gold webs you "
    "see are those chains. Most are tiny, but the biggest one here ran "
    "through {cmax} countries at once.\n\n"
    "Kempe thought this trick proved the whole theorem, and everyone believed "
    "him for eleven years, until Percy Heawood showed in 1890 that it can "
    "fail. It fails here too: the simple swap got stuck {stuck} times, and "
    "those spots needed a full exhaustive search of the countries around "
    "them. Closing that gap is what eventually took a computer: instead of "
    "one trick, the 1976 proof had to check 1,482 separate configurations.\n\n"
    "Why not three colours? Because {odd} of these countries sit inside an "
    "odd ring of neighbours, and a single one of those is enough to force a "
    "fourth colour. That was checked by brute force, trying every one of the "
    "3 to the power {w1} ways to use three colours on one such ring and its "
    "centre: {w3} of them work.\n\n"
    "Checked before anything was drawn: all {edges} borders separate "
    "different colours, and so do {corners} places where countries nearly "
    "touch at a corner. Every contact that actually appears on screen, at "
    "two resolutions, was verified too. The final sweep shows it: {edges} "
    "borders, zero clashes, four colours.\n\n"
    "And the story is still moving. In September 2026 Quanta reported a "
    "brand new proof by Thorup, Thomassen, Kawarabayashi, Mohar and "
    "colleagues. It still leans on a computer, with 8,202 configurations "
    "against 1,482 in 1976 and 633 in 1997, but it gives a far faster way to "
    "colour a map: about n log n steps instead of n squared."
)

TAGS_EXTRA = [
    "four color theorem", "graph theory", "map coloring", "kempe chains",
    "planar graph", "computer proof", "combinatorics", "topology",
    "algorithms", "famous proofs", "math history", "voronoi",
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
    return BODY_TMPL.format(
        n=f"{ev['n']:,}", cmax=ev["chain_max"], stuck=len(ev["stuck"]),
        odd=v["odd_wheels"], w1=v["wheel_size"] + 1, w3=v["wheel_3"],
        edges=f"{v['edges']:,}", corners=v["corners"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_four_color_short.py")

    description = build_description(
        body(), hashtags=["#fourcolortheorem", "#graphtheory", "#maps", "#proof"]
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
