"""Sube el short 'Cerebro real de mosca' (15s, 1080x1920) PROGRAMADO.

    python upload_fly_brain_short.py
    python upload_fly_brain_short.py --now      # unlisted ya, sin programar
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

VIDEO = os.path.join(REPO, "output", "shorts_fly_brain",
                     "shorts_fly_brain_branded.mp4")
EVENTS = os.path.join(REPO, "data", "shorts_fly_brain_events.json")

CHILE_UTC_OFFSET = -4
PUBLISH_HOUR = 8

TITLE = "Watch A Real Fly Brain Decide To Jump 🪰 #math #shorts"

BODY_TMPL = (
    "Every glowing dot here is a real neuron, at its real position, from a "
    "real fly. In September 2026 Janelia's FlyEM team, the Cambridge "
    "Connectomics group and Google Research published MaleCNS v1.0: the "
    "complete wiring of a male fruit fly's brain and nerve cord. "
    "{neurons} neurons. {synapses} synapses. Every one mapped.\n\n"
    "You may have seen simulated fly brains playing Beat Saber this month. "
    "This is the same kind of model, run on that new map. Each neuron is "
    "one equation: its voltage leaks back toward rest, climbs when its "
    "inputs push it, and fires when it crosses a threshold.\n\n"
    "tau dV/dt = V0 - V + g\n\n"
    "When a neuron fires, every neuron it connects to gets a kick sized by "
    "the number of synapses between them, positive or negative depending "
    "on the chemical it releases. The parameters are the published ones "
    "from Shiu and colleagues, Nature 2024.\n\n"
    "Then something looms. The {nstim} neurons in the eyes that detect an "
    "approaching object are switched on, and the wiring does the rest. "
    "In this simulation the Giant Fiber, the fly's famous escape neuron, "
    "fires {gf:.1f} milliseconds later, and the motor neuron that fires the "
    "jump muscle, down in the nerve cord, fires at {jump:.1f} ms. It is the "
    "escape circuit, emerging from the map alone: nobody told the model "
    "which neurons to use. The motor neuron for feeding, as a control, "
    "stays completely silent. By {tend:.0f} ms, {active} neurons have fired.\n\n"
    "Checked, not assumed: the integrator reproduces the exact formula for "
    "a single synaptic kick to within {psp:.0e} millivolts, and a neuron "
    "under constant drive fires at {rs:.2f} Hz against the textbook "
    "{ra:.2f} Hz, off by one time step. The escape sequence repeats with "
    "a different random stimulus: Giant Fiber at {gf2:.1f} ms, jump at "
    "{jump2:.1f} ms, feeding silent again.\n\n"
    "Honest limits: this is a model, not a living fly. Real neurons are "
    "richer than one equation, and part of the real Giant Fiber connection "
    "is electrical, which a chemical-synapse model leaves out. About "
    "{nosoma} neurons have no recorded cell-body position in the dataset, "
    "most of them sensory neurons whose cell bodies sit outside the nervous "
    "system, in the eyes, legs and mouthparts. Those are drawn at the "
    "centre of their connections.\n\n"
    "Data: FlyEM MaleCNS v1.0, Janelia Research Campus, CC-BY 4.0. Model: "
    "Shiu et al., A Drosophila computational brain model reveals "
    "sensorimotor processing, Nature 2024."
)

TAGS_EXTRA = [
    "fly brain", "connectome", "neuroscience", "brain simulation",
    "drosophila", "janelia", "giant fiber", "spiking neural network",
    "computational neuroscience", "maleCNS", "neurons", "escape reflex",
]


def _default_publish_at() -> str:
    local = (datetime.now() + timedelta(days=1)).replace(
        hour=PUBLISH_HOUR, minute=0, second=0, microsecond=0)
    utc = local - timedelta(hours=CHILE_UTC_OFFSET)
    return utc.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def body() -> str:
    with open(EVENTS, encoding="utf-8") as fh:
        ev = json.load(fh)
    st, v, c = ev["stats"], ev["verify"], ev["circuit"]
    return BODY_TMPL.format(
        neurons=f"{st['neurons']:,}", synapses=f"{st['synapses']:,}",
        nstim=ev["n_stim"], gf=ev["first_gf_ms"], jump=ev["first_jump_ms"],
        tend=ev["shown"][-1]["bio_ms"], active=f"{ev['shown'][-1]['active']:,}",
        psp=v["psp_err"], rs=v["rate_sim"], ra=v["rate_ana"],
        gf2=c[1][0], jump2=c[1][1],
        nosoma=f"{st['neurons'] - ev['somas']:,}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish-at", default=None, help="ISO 8601 UTC")
    ap.add_argument("--now", action="store_true", help="Subir unlisted ya")
    a = ap.parse_args()

    if not os.path.isfile(VIDEO):
        sys.exit(f"No existe el video: {VIDEO}\n  python build_fly_brain_short.py")

    description = build_description(
        body(), hashtags=["#neuroscience", "#connectome", "#brain", "#flybrain"]
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
