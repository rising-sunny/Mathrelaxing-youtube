"""Sube el short 'Doble rendija' (15s, 1080x1920) PROGRAMADO.

    python upload_double_slit_short.py
    python upload_double_slit_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_slit",
                     "shorts_slit_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_slit_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "One Electron Goes Through Both Slits 🌊 #physics #shorts"

BODY_TMPL = (
    "Feynman called it the only mystery of quantum mechanics.\n\n"
    "Fire ONE electron at a wall with two slits. What travels is not a little "
    "ball but a wave, and that wave goes through both slits at once. The two "
    "halves overlap on the other side and interfere: where crest meets crest "
    "the wave grows, where crest meets trough it cancels. Those dark rays in "
    "the fan are places the electron is forbidden to land.\n\n"
    "Then it hits the detector, and the wave is gone. One dot. One place. "
    "Nothing about that single dot looks like a wave.\n\n"
    "Now repeat it {n:,} times. Every dot is a separate electron, and yet "
    "together they draw the stripes of the wave that no single electron "
    "ever showed you.\n\n"
    "This is not an animation of the idea. It is the Schrodinger equation\n\n"
    "i hbar dpsi/dt = -hbar^2/(2m) laplacian(psi) + V psi\n\n"
    "solved numerically on a {nx} by {ny} grid with the split-step Fourier "
    "method. The colour is the phase of psi, the brightness its size. The "
    "dots are not placed by hand either: the flow of probability through "
    "the detector line was measured during the simulation, and each "
    "electron lands at a random spot drawn from that measured distribution. "
    "Only {tr:.0f}% of the wave makes it through the slits at all; the rest "
    "bounces back, which is the blue glow at the bottom at the end.\n\n"
    "Checked before a single frame was drawn:\n\n"
    "Probability is conserved: the total stays at 1 to within {ne:.0e}.\n\n"
    "A free wave packet spreads exactly as the textbook formula says, "
    "sigma(t) = sigma0 sqrt(1 + (hbar t / 2 m sigma0^2)^2), to {sr:.0e}.\n\n"
    "Energy stays constant while the wave slams into the wall, to "
    "{ed:.1%}.\n\n"
    "And the bright fringes land where the two-slit formula puts them, "
    "cos^2(pi d sin(theta) / lambda) under the single-slit envelope: "
    "{npk} maxima, spaced about {fr:.0f} pixels apart as lambda L / d "
    "predicts, all within {fe:.0%} of a fringe of the formula.\n\n"
    "Tonomura's team did this with real electrons in 1989, one at a time, "
    "and the dots built up exactly like this."
)

TAGS_EXTRA = [
    "double slit experiment", "quantum mechanics", "wave particle duality",
    "schrodinger equation", "electron interference", "wave function collapse",
    "feynman", "quantum physics", "interference pattern", "tonomura",
    "split step fourier", "physics simulation",
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
        n=ev["ndots"], nx=ev["grid"][1], ny=ev["grid"][0],
        tr=ev["transmitted"] * 100, ne=v["norm_err"], sr=v["sigma_rel"],
        ed=v["energy_drift"], npk=len(ev["peaks_px"]), fr=ev["fringe_px"],
        fe=max(ev["fringe_err"], 0.01))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_double_slit_short.py")

    description = build_description(
        body(), hashtags=["#quantum", "#physics", "#doubleslit", "#science"]
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
