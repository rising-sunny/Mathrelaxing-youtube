"""Sube el short 'Pulsar' (15s, 1080x1920) PROGRAMADO.

    python upload_pulsar_short.py
    python upload_pulsar_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_pulsar", "shorts_pulsar_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_pulsar_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "You Have Seen This On A T-Shirt 🌌 The Maths Behind It #math #shorts"

BODY_TMPL = (
    "A neutron star the size of a city spins with its magnetic axis tilted "
    "away from its rotation axis. The beam sweeps past us once per turn, like "
    "a lighthouse. PSR B1919+21 — the first one ever found, by Jocelyn Bell "
    "in 1967 — does it every {period} seconds.\n\n"
    "Every line in the stack is one rotation. Look at them individually and "
    "they are a mess: the pulse changes height, width and arrival phase from "
    "one turn to the next, and half of what you see is receiver noise.\n\n"
    "Now add them up. The pulse is in the same place every time so it grows "
    "like N. The noise is random so it only grows like the square root of N. "
    "Divide and you get the whole reason radio astronomy works:\n\n"
    "S/N ∝ √N\n\n"
    "Measured here, not quoted: fitting the folded signal-to-noise against N "
    "over independent realisations gives an exponent of {exp:.3f} with "
    "R² = {r2:.4f}. The single rotation at the start has a peak {s1:.1f} times "
    "the noise. By {rows} rotations the average profile is at {sn:.0f}.\n\n"
    "There is a catch, and it is brutal. You have to know the period first. "
    "Fold 400 rotations at exactly the right period and the peak sits at "
    "{good:.0f} times the noise. Get the period wrong by one part in a "
    "thousand and it collapses to {bad:.1f} — the pulse smears across the "
    "whole rotation and vanishes. Finding pulsars means searching millions of "
    "trial periods, which is why the first ones were found by a graduate "
    "student staring at chart paper.\n\n"
    "And the shape at the end: eighty stacked pulses of this exact pulsar are "
    "the cover of Joy Division's Unknown Pleasures. The plot came from Harold "
    "Craft's 1970 Cornell thesis by way of the Cambridge Encyclopaedia of "
    "Astronomy, and the band never credited it.\n\n"
    "The signal here is simulated from the standard model — Gaussian pulse "
    "with log-normal variability plus band-limited noise — using the real "
    "spin period. It is not archive data. The star itself turns in real "
    "time, one rotation every {period} seconds; only the stack below it is "
    "compressed, about {sp:.0f} to 1."
)

TAGS_EXTRA = [
    "pulsar", "neutron star", "radio astronomy", "signal to noise",
    "unknown pleasures", "joy division", "jocelyn bell", "psr b1919+21",
    "folding", "astrophysics", "signal processing", "lighthouse model",
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
        period=ev["period_s"], exp=ev["exponent"], r2=ev["fit_r2"],
        s1=ev["snr_shown"][0], rows=ev["rows"], sn=ev["snr_shown"][-1],
        good=ev["snr_good_400"], bad=ev["snr_bad"]["0.001"], sp=ev["speedup"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_pulsar_short.py")

    description = build_description(
        body(), hashtags=["#pulsar", "#astrophysics", "#neutronstar", "#space"]
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
