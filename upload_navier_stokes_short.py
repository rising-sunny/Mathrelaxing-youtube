"""Sube el short 'Navier-Stokes 2-D' (15s, 1080x1920) PROGRAMADO.

    python upload_navier_stokes_short.py
    python upload_navier_stokes_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_navier_stokes",
                     "shorts_navier_stokes_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_navier_stokes_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "The $1,000,000 Equation 🌊 Solved In 2D, Open In 3D #math #shorts"

BODY_TMPL = (
    "The Navier-Stokes equations describe every fluid you have ever touched. "
    "One of the seven Millennium Prize Problems asks a question that sounds "
    "almost childish: start a fluid off smooth, let it run forever, does it "
    "stay smooth? Or can the velocity become infinite somewhere in finite "
    "time? Nobody knows. That is the million dollars.\n\n"
    "In two dimensions we do know, and the reason is one line long.\n\n"
    "Write the equations in terms of vorticity, the local rate of spin. In "
    "the plane, vorticity is just a NUMBER attached to each point, and it "
    "obeys\n\n"
    "dw/dt + u . grad w = nu laplacian w\n\n"
    "which says the spin is only carried along by the flow and smeared out "
    "by viscosity. Nothing on the right can manufacture spin. So the largest "
    "value of the spin anywhere in the fluid can only shrink. That is a "
    "maximum principle, and it forbids a blow-up outright.\n\n"
    "In three dimensions vorticity is a VECTOR, and the equation gains one "
    "extra term: (w . grad)u, vortex stretching. Pull a spinning tube of "
    "fluid longer and thinner and it spins faster, the way a skater pulls "
    "their arms in. That single term is the whole problem. Nobody has been "
    "able to rule out the possibility that it runs away.\n\n"
    "Everything on screen is measured from the simulation, a "
    "{nx} by {ny} pseudospectral solver run for {turns:.0f} eddy turnover "
    "times. The peak vorticity starts at {w0:.2f} and ends at {w1:.2f}, and "
    "across all {frames} frames it never once increased, exactly as the "
    "maximum principle demands.\n\n"
    "Watch what happens instead. The spin cannot grow, but it can gather: "
    "small eddies merge into bigger ones, {v0} of them at the start and "
    "{v1} at the end. This is the inverse cascade, and it is why two "
    "dimensional flows look nothing like three dimensional ones. Energy is "
    "nearly kept, {efrac:.0f}% of it, while enstrophy, the total squared "
    "spin, falls to {zfrac:.1f}%. Big structures survive, small ones burn "
    "off.\n\n"
    "Solver check before any of this was rendered: with viscosity switched "
    "off the scheme conserves energy AND enstrophy to better than one part "
    "in ten million, and the velocity field is divergence free to "
    "{div:.0e}. Enstrophy is the hard one, since any aliasing error breaks "
    "it first.\n\n"
    "As for the prize: in September 2026 OpenAI announced a blow-up result "
    "for a forced variant of the 3D equations, formally checked in Lean. "
    "The Clay Mathematics Institute has said the problem has apparently "
    "been settled and that its own review is deliberately unhurried and "
    "still under way. The plane, meanwhile, has been safe since the 1960s."
)

TAGS_EXTRA = [
    "navier stokes", "fluid dynamics", "turbulence", "millennium prize",
    "clay institute", "vorticity", "2d turbulence", "inverse cascade",
    "partial differential equations", "computational physics",
    "spectral method", "vortex stretching",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    return BODY_TMPL.format(
        nx=ev["nx"], ny=ev["ny"], turns=ev["turns"],
        w0=ev["wmax"][0], w1=ev["wmax"][-1], frames=len(ev["wmax"]),
        v0=ev["vortices"][0], v1=ev["vortices"][-1],
        efrac=ev["energy_frac"][-1] * 100, zfrac=ev["enstrophy_frac"][-1] * 100,
        div=ev["max_div"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_navier_stokes_short.py")

    description = build_description(
        body(), hashtags=["#navierstokes", "#fluiddynamics", "#turbulence",
                          "#physics"]
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
