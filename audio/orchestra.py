"""
Orquesta con instrumentos muestreados: partitura -> MIDI -> FluidSynth.

La sintesis de audio/ambient_score.py (senos y dientes de sierra) suena a
sintetizador por mas que se la trabaje. Aqui la misma idea -- una partitura
escrita, sincronizada con los golpes del video -- la tocan muestras de
instrumentos reales del banco MuseScore General (licencia MIT).

Bucle exacto: se escriben TRES vueltas de la partitura y se queda la del
medio. Asi las colas de reverb del final de una vuelta ya estan sonando al
principio de la siguiente, igual que en el bucle del Short.

Formato de la partitura (tiempos en pulsos; `beats` pulsos duran `duration`):
    {"beats": 24,
     "tracks": [{"program": 48, "vol": 100, "pan": 64,
                 "notes": [(pulso, duracion, nota_midi, velocidad), ...],
                 "expr": [(pulso, 0..127), ...]}],          # opcional
     "drums": [(pulso, nota_gm, velocidad), ...]}           # canal 10

Uso:
    python audio/orchestra.py --score shatter --outdir output/x --duration 15
"""
import argparse
import os
import subprocess
import sys
import tempfile
import wave

import mido
import numpy as np

SR = 48000
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SF_DIR = os.path.join(REPO, "data", "soundfonts")
SF_URL = ("https://ftp.osuosl.org/pub/musescore/soundfont/MuseScore_General/"
          "MuseScore_General.sf2")
SF_PATH = os.path.join(SF_DIR, "MuseScore_General.sf2")

NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def n(name):
    """'A4' -> 69, 'Bb3' -> 58, 'F#5' -> 78"""
    base = NAMES[name[0]]
    i = 1
    while i < len(name) and name[i] in "#b":
        base += 1 if name[i] == "#" else -1
        i += 1
    return base + 12 * (int(name[i:]) + 1)


def fetch_soundfont():
    if not os.path.isfile(SF_PATH):
        os.makedirs(SF_DIR, exist_ok=True)
        print(f"[orq] descargando banco de sonidos -> {SF_PATH}")
        subprocess.run(["curl", "-sSL", "-o", SF_PATH, SF_URL], check=True)
    return SF_PATH


def to_midi(score, duration, cycles=3):
    beats = score["beats"]
    tpb = 960
    mid = mido.MidiFile(ticks_per_beat=tpb)
    tempo = int(round(duration / beats * 1e6))            # microsegundos por pulso
    evs = {}                                              # canal -> [(tick, msg)]

    def add(ch, tick, msg):
        evs.setdefault(ch, []).append((int(round(tick)), msg))

    chans = [c for c in range(16) if c != 9]
    for k, tr in enumerate(score["tracks"]):
        ch = chans[k]
        add(ch, 0, mido.Message("program_change", channel=ch, program=tr["program"]))
        add(ch, 0, mido.Message("control_change", channel=ch, control=7, value=tr.get("vol", 100)))
        add(ch, 0, mido.Message("control_change", channel=ch, control=10, value=tr.get("pan", 64)))
        add(ch, 0, mido.Message("control_change", channel=ch, control=91, value=tr.get("reverb", 70)))
        for c in range(cycles):
            off = c * beats * tpb
            for b, v in tr.get("expr", []):
                add(ch, off + b * tpb, mido.Message("control_change", channel=ch,
                                                    control=11, value=int(v)))
            for b, d, note, vel in tr["notes"]:
                add(ch, off + b * tpb, mido.Message("note_on", channel=ch, note=note, velocity=int(vel)))
                add(ch, off + (b + d) * tpb - 1, mido.Message("note_off", channel=ch, note=note, velocity=0))
    for c in range(cycles):
        off = c * beats * tpb
        for b, note, vel in score.get("drums", []):
            add(9, off + b * tpb, mido.Message("note_on", channel=9, note=note, velocity=int(vel)))
            add(9, off + b * tpb + tpb // 8, mido.Message("note_off", channel=9, note=note, velocity=0))

    meta = mido.MidiTrack()
    meta.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    mid.tracks.append(meta)
    for ch, lst in evs.items():
        # a igual tick, primero los note_off: si no, una nota repetida se corta
        lst.sort(key=lambda e: (e[0], e[1].type != "note_off"))
        trk = mido.MidiTrack()
        last = 0
        for tick, msg in lst:
            trk.append(msg.copy(time=tick - last))
            last = tick
        mid.tracks.append(trk)
    return mid


def render(score, duration, out_path, gain=0.5):
    sf = fetch_soundfont()
    with tempfile.TemporaryDirectory() as tmp:
        mpath = os.path.join(tmp, "score.mid")
        wpath = os.path.join(tmp, "raw.wav")
        to_midi(score, duration).save(mpath)
        subprocess.run(["fluidsynth", "-ni", "-q", "-g", str(gain), "-r", str(SR),
                        "-o", "synth.reverb.room-size=0.75", "-o", "synth.reverb.level=0.6",
                        "-F", wpath, sf, mpath], check=True)
        with wave.open(wpath) as w:
            ch = w.getnchannels()
            raw = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64)
    x = raw.reshape(-1, ch) / 32768.0
    n0 = int(round(duration * SR))
    seg = x[n0:2 * n0]                                   # la vuelta del medio
    assert len(seg) == n0, "fluidsynth no llego a la segunda vuelta"
    peak = np.max(np.abs(seg)) or 1.0
    data = (seg / peak * 0.92 * 32767).astype(np.int16)
    with wave.open(out_path, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return seg / peak


# --------------------------------------------------------------- partituras
def score_shatter():
    """Cuatro materiales (short MPM). Re menor, i-VI-iv-V (Dm-Bb-Gm-A), 24
    pulsos en 15 s (96 BPM). Golpes donde pasa algo en el video: gelatina
    contra el poste 0.7 s (pulso 1.12), nieve 2.6 s (4.16), se abre la
    arena 4.0 s (6.4), compuerta 7.4 s (11.84), la caja se inclina 10.6 s
    (16.96) y vuelve 13.2 s (21.12)."""
    B = 24
    HITS = [1.12, 4.16, 6.4, 11.84, 16.96, 21.12]
    tracks = []
    prog = [["D3", "A3", "D4", "F4"], ["Bb2", "F3", "Bb3", "D4"],
            ["G2", "D3", "G3", "Bb3"], ["A2", "E3", "A3", "C#4"]]
    notes = []
    for i, ch in enumerate(prog):
        for p in ch:
            notes.append((i * 6, 6, n(p), 72))
    tracks.append({"program": 48, "vol": 96, "pan": 50, "notes": notes,
                   "expr": [(0, 62), (6, 80), (11.84, 118), (17, 110), (21, 122), (23.5, 70)]})
    # ostinato en corcheas: pizzicato que crece hasta la ola
    ost = []
    roots = ["D3", "Bb2", "G2", "A2"]
    for q in range(B * 2):
        b = q * 0.5
        r = n(roots[int(b // 6)])
        step = [0, 12, 7, 12][q % 4]
        vel = 72 + (22 if q % 4 == 0 else 0) + int(24 * min(1, b / 11.84))
        ost.append((b, 0.45, r + step, min(vel, 122)))
    tracks.append({"program": 45, "vol": 112, "pan": 40, "notes": ost})
    # trompas: el tema, que se hace grande cuando se abre la compuerta
    theme = [(0, 3, "A4"), (3, 1.5, "F4"), (4.5, 1.5, "D4"), (6, 3, "D5"), (9, 2.84, "C5"),
             (11.84, 2.16, "Bb4"), (14, 1, "A4"), (15, 2, "D5"), (17, 1, "G5"), (18, 2, "E5"),
             (20, 1, "C#5"), (21.12, 1.4, "E5"), (22.5, 1.5, "A4")]
    tracks.append({"program": 60, "vol": 104, "pan": 76,
                   "notes": [(b, d, n(p), 100 if b >= 11.84 else 78) for b, d, p in theme],
                   "expr": [(0, 72), (11.84, 124), (23, 84)]})
    # trompetas doblando arriba solo en la parte grande
    tracks.append({"program": 56, "vol": 84, "pan": 88,
                   "notes": [(b, d, n(p) + 12, 88) for b, d, p in theme if 11.84 <= b < 22]})
    # celesta: brillos en cada suceso
    cel = ["D6", "A6", "F6", "D6", "G6", "E6"]
    tracks.append({"program": 8, "vol": 92, "pan": 90,
                   "notes": [(b, 1, n(p), 92) for b, p in zip(HITS, cel)]})
    # timbales en cada suceso, mas fuertes en la ola y en la inclinacion
    tim = [(HITS[0], "D2", 112), (HITS[1], "D2", 108), (HITS[2], "A1", 96),
           (HITS[3], "D2", 127), (HITS[3] + 0.5, "D2", 104), (HITS[4], "G1", 122),
           (HITS[5], "A1", 124)]
    tracks.append({"program": 47, "vol": 118, "pan": 64,
                   "notes": [(b, 1, n(p), v) for b, p, v in tim]})
    drums = [(HITS[0], 49, 104), (HITS[1], 57, 104), (HITS[3], 49, 127),
             (HITS[3], 36, 127), (HITS[4], 57, 118), (HITS[5], 49, 120)]
    for k in range(8):                              # redoble antes de la ola
        drums.append((HITS[3] - 1.0 + 0.125 * k, 38, 52 + 9 * k))
    b = 12.0
    while b < 24:                                   # bombo desde la ola
        drums.append((b, 36, 104 if b % 1 == 0 else 78))
        b += 0.5
    return {"beats": B, "tracks": tracks, "drums": drums}


SCORES = {"shatter": score_shatter}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", required=True, choices=sorted(SCORES))
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--name", default="music.wav")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    path = os.path.join(a.outdir, a.name)
    render(SCORES[a.score](), a.duration, path)
    print(f"[orq] {a.duration:.2f}s | partitura {a.score} | bucle exacto -> {path}")


if __name__ == "__main__":
    sys.exit(main())
