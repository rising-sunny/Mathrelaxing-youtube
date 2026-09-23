"""Sube el short 'Luciernagas de Kuramoto' (15s, 1080x1920) PROGRAMADO.

    python upload_kuramoto_short.py
    python upload_kuramoto_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_kuramoto",
                     "shorts_kuramoto_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_kuramoto_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Thousands Of Fireflies, No Leader, Perfect Sync ✨ #math #shorts"

BODY_TMPL = (
    "In a few forests in Southeast Asia and the Smoky Mountains, thousands "
    "of fireflies flash together, in time, all night. Nobody is conducting. "
    "Each one only sees its neighbours. So how does the whole forest agree?\n\n"
    "In 1975 Yoshiki Kuramoto wrote down the simplest possible answer. Every "
    "firefly is a clock with its own natural speed, and each one nudges its "
    "phase a little toward everyone else's:\n\n"
    "dtheta_i/dt = omega_i + K r sin(psi - theta_i)\n\n"
    "Here r measures how lined up the whole swarm is, from 0 (total chaos) "
    "to 1 (perfect unison), and K is how strongly they listen to each other. "
    "Watch the circle at the bottom: every dot is one firefly, and the arrow "
    "is r. When the dots bunch at the top, the forest flashes.\n\n"
    "The astonishing part is that there is a sharp threshold. Below a "
    "critical coupling Kc, nothing happens at all: r stays at zero. Above it, "
    "order switches on, and for a Lorentzian spread of natural frequencies "
    "the answer is exact:\n\n"
    "r = square root of (1 - Kc / K),   Kc = 2 gamma\n\n"
    "That was checked, not quoted. A sweep with {nsw} simulated fireflies "
    "starting from random phases matches the formula to within {dev:.0e} at "
    "every coupling above threshold, and a straight line fit of r squared "
    "against 1/K returns an intercept of {fa:.4f} and a critical coupling "
    "of {fkc:.4f} times the prediction. Below threshold r never gets above "
    "{below:.3f}, which is just the noise of a finite swarm.\n\n"
    "In this video the coupling climbs from 0 to {kmax:.0f} times Kc. Notice "
    "the delay: just past Kc the swarm does NOT sync immediately. Chaos is "
    "still a steady state there, only an unstable one, and the swarm has to "
    "be pushed off it by its own random fluctuations, which start out tiny. "
    "Then it snaps. By the end r is {rf:.3f} against an exact {re:.3f}, and "
    "{lk:.0f} percent of the fireflies are locked. The rest have natural "
    "rhythms too far from the crowd, and they keep blinking on their own, "
    "exactly as the theory says they must.\n\n"
    "One more thing. Shifting every phase by the same amount gives another "
    "perfectly valid solution, so that freedom was used to put the swarm on "
    "the beat of the music. Once synchronised, the forest flashes on every "
    "pulse to within {ms:.1f} milliseconds."
)

TAGS_EXTRA = [
    "fireflies", "synchronization", "kuramoto model", "coupled oscillators",
    "phase transition", "emergence", "complex systems", "self organization",
    "nonlinear dynamics", "order parameter", "collective behavior", "strogatz",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    v, last = ev["verify"], ev["shown"][-1]
    return BODY_TMPL.format(
        nsw=v["n_sweep"], dev=v["max_dev"], fa=v["fit_a"], fkc=v["fit_kc"],
        below=v["below"], kmax=ev["kmax_over_kc"], rf=last["r"],
        re=last["r_exact"], lk=last["locked"] * 100, ms=ev["beat_ms"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_kuramoto_short.py")

    description = build_description(
        body(), hashtags=["#fireflies", "#synchronization", "#physics", "#nature"]
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
