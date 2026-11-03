#!/usr/bin/env python3
"""Original melodic ambient synthesis. Requires NumPy and FFmpeg."""
import argparse
import json
import subprocess
import tempfile
import wave
from pathlib import Path
import numpy as np

SR = 48000

def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)

def envelope(n, attack, release):
    env = np.ones(n)
    a, r = min(int(attack * SR), n), min(int(release * SR), n)
    if a: env[:a] *= np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    if r: env[-r:] *= np.sin(np.linspace(np.pi / 2, 0, r)) ** 2
    return env

def render(duration, seed):
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    audio = np.zeros((n, 2), dtype=np.float64)
    shift = [0, 2, -3][seed % 3]
    chords = [[48,55,58,62,63], [44,51,55,60], [51,58,62,65], [46,53,60,62]]
    motif = [67,63,62,60,63]
    # Preserve a recognizable contour; choose a small original variation per seed.
    motif[2] += int(rng.choice([0, 0, 1]))
    notes = []
    def add(start, signal, pan):
        offset = int(start * SR)
        count = min(len(signal), n - offset)
        if count <= 0: return
        audio[offset:offset+count, 0] += signal[:count] * np.cos(pan*np.pi/2)
        audio[offset:offset+count, 1] += signal[:count] * np.sin(pan*np.pi/2)
    segment = duration / 4
    for i, chord in enumerate(chords):
        length = segment + 1.3
        t = np.arange(int(length * SR)) / SR
        env = envelope(len(t), .8, 1.3)
        for j, note in enumerate(chord):
            f = hz(note + shift)
            phase = rng.uniform(0, 2*np.pi)
            tone = (np.sin(2*np.pi*f*t + phase)
                    + .32*np.sin(2*np.pi*f*1.0015*t + phase)
                    + .12*np.sin(2*np.pi*2*f*t + phase))
            add(i*segment, .045*tone*env, .2 + .6*j/max(1,len(chord)-1))
        bass = .065*np.sin(2*np.pi*hz(chord[0]-12+shift)*t)
        add(i*segment, bass*env, .5)
    beats = [.5, 2, 3.5, 5, 6.5, 8, 9.5, 11, 12.5, 14, 15.5, 17]
    for i, beat in enumerate(beats):
        start = beat / 18 * duration
        note = motif[i % len(motif)] + shift
        if i == len(beats)-1: note = 60 + shift
        length = min(2.7, duration-start)
        t = np.arange(int(length*SR)) / SR
        f = hz(note)
        voice = (np.sin(2*np.pi*f*t) + .18*np.sin(2*np.pi*2*f*t)
                 + .045*np.sin(2*np.pi*3*f*t))
        voice *= np.exp(-1.15*t)*envelope(len(t), .06, .55)*.2
        add(start, voice, .4 if i%2 else .6)
        notes.append({'start_seconds':round(start,3),'midi':note})
    dry = audio.copy()
    for seconds, gain in [(.28,.19),(.43,.14),(.71,.1),(1.03,.065)]:
        delay = int(seconds*SR)
        if delay < n: audio[delay:] += dry[:-delay, ::-1]*gain
    audio *= envelope(n, .45, 1.4)[:,None]
    peak = np.max(np.abs(audio))
    if peak: audio *= .75/peak
    assert np.isfinite(audio).all()
    return audio, notes

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--duration',type=float,default=18)
    ap.add_argument('--seed',type=int,default=61000)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    if not 10 <= a.duration <= 30: ap.error('Duration must be 10–30 seconds')
    if a.out.suffix.lower() not in ['.wav','.mp3']: ap.error('Use .wav or .mp3')
    if a.out.exists() or a.out.with_suffix('.music.json').exists():
        ap.error('Output or composition record already exists; choose another name')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    audio, notes=render(a.duration,a.seed)
    with tempfile.TemporaryDirectory() as folder:
        raw=Path(folder)/'raw.wav'
        with wave.open(str(raw),'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((audio*32767).astype('<i2').tobytes())
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n',
                        '-i',str(raw),'-af','loudnorm=I=-16:TP=-1.5:LRA=7',
                        '-ar',str(SR),str(a.out)],check=True)
    a.out.with_suffix('.music.json').write_text(json.dumps({
        'seed':a.seed,'duration_seconds':a.duration,'sample_rate':SR,
        'description':'Original procedurally generated melodic ambient music',
        'external_samples':False,'melody':notes,
        'composition_version':1},indent=2)+'\n')
    print('Created:',a.out)

if __name__=='__main__': main()
