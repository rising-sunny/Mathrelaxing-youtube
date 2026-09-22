"""Sube el short 'Orbitales del hidrogeno' (15s, 1080x1920) PROGRAMADO.

    python upload_hydrogen_short.py
    python upload_hydrogen_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_hydrogen",
                     "shorts_hydrogen_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_hydrogen_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "The Only Atom Maths Can Solve Exactly ⚛️ #math #shorts"

BODY_TMPL = (
    "One proton, one electron. That is the entire system, and it is the "
    "last one anybody can solve with pen and paper. Add a single extra "
    "electron and the exact solution is gone forever.\n\n"
    "For hydrogen the answer separates perfectly into a radial part and an "
    "angular part:\n\n"
    "psi(r, theta, phi) = R(r) times Y(theta, phi)\n\n"
    "R is an associated Laguerre polynomial times a decaying exponential. "
    "Y is a spherical harmonic. Three integers pick the state: n, which "
    "sets the energy, l, which sets the shape, and m, which sets the "
    "orientation.\n\n"
    "What you are watching is not an artist's impression. It is that "
    "formula sampled on a {nv} by {nv} by {nv} grid and integrated through, "
    "eight states from 1s up to 7i. The colour is the SIGN of psi, not its "
    "size. That sign is not decoration: when two atoms meet, lobes of "
    "matching sign reinforce and lobes of opposite sign cancel, and that is "
    "the difference between a chemical bond and no bond at all.\n\n"
    "Three things were checked before a single frame was drawn, for all 28 "
    "states with n up to 7:\n\n"
    "The total probability integrates to 1, to within {norm:.0e}.\n\n"
    "The radial part has exactly n minus l minus 1 zero crossings. Not "
    "approximately. Every one of the 28.\n\n"
    "And the real test: applying the radial Hamiltonian numerically, by "
    "plain finite differences, and reading off the eigenvalue. It comes "
    "back as minus 1 over 2n squared in atomic units, the Rydberg formula, "
    "to {erel:.0e} relative error. States with different n are orthogonal "
    "to {orth:.0e}.\n\n"
    "Watch the size counter. The box grows from {b0:.0f} to {b1:.0f} Bohr "
    "radii across the eight states. The mean radius of an orbital is "
    "(3n squared minus l(l+1)) / 2, so it swells roughly with the square "
    "of n, tempered by the angular momentum. Measured on what you can "
    "actually see, the last state is about {ratio:.0f} times wider than "
    "the first. That swelling is why loosely bound electrons are the ones "
    "that do chemistry.\n\n"
    "And the energies climb toward zero like 1 over n squared, from "
    "{e0:.2f} eV down to {e1:.2f} eV. Zero is where the electron escapes. "
    "The whole visible spectrum of hydrogen, every line Balmer measured in "
    "1885, is just differences between the numbers on this screen."
)

TAGS_EXTRA = [
    "hydrogen atom", "quantum mechanics", "atomic orbitals", "schrodinger",
    "spherical harmonics", "wavefunction", "volume rendering", "chemistry",
    "quantum numbers", "rydberg", "laguerre polynomials", "electron orbitals",
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
        nv=ev["nv"], norm=ev["worst_norm"], erel=ev["worst_energy_rel"],
        orth=ev["orthogonality"], b0=ev["boxes"][0], b1=max(ev["boxes"]),
        e0=ev["shown"][0]["energy_ev"], e1=ev["shown"][-1]["energy_ev"],
        ratio=max(ev["boxes"]) / ev["boxes"][0])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_hydrogen_short.py")

    description = build_description(
        body(), hashtags=["#quantum", "#chemistry", "#physics", "#atom"]
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
