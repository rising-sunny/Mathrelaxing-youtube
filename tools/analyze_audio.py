import os
import json
import argparse
import numpy as np
import librosa
import librosa.display

def normalize(x, min_val, max_val):
    x_norm = (x - np.min(x)) / (np.max(x) - np.min(x) + 1e-8)
    return min_val + x_norm * (max_val - min_val)

def smooth(x, window_len=11, window='hanning'):
    if x.ndim != 1:
        raise ValueError("smooth only accepts 1 dimension arrays.")
    if x.size < window_len:
        raise ValueError("Input vector needs to be bigger than window size.")
    if window_len<3:
        return x
    if not window in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
        raise ValueError("Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'")
    s = np.r_[x[window_len-1:0:-1], x, x[-2:-window_len-1:-1]]
    if window == 'flat':
        w = np.ones(window_len,'d')
    else:
        w = eval('np.' + window + '(window_len)')
    y = np.convolve(w/w.sum(), s, mode='valid')
    return y[(window_len//2-1):-(window_len//2)]

def main():
    parser = argparse.ArgumentParser(description="Analyze audio to drive Chladni simulation")
    parser.add_argument("--input", type=str, required=True, help="Path to input audio file")
    parser.add_argument("--output", type=str, default="data/audio_driven_events.json")
    parser.add_argument("--fps", type=int, default=60, help="Frames per second")
    args = parser.parse_args()

    print(f"Loading audio from {args.input}...")
    y, sr = librosa.load(args.input, sr=None)
    duration = librosa.get_duration(y=y, sr=sr)
    frames_total = int(duration * args.fps)
    print(f"Audio duration: {duration:.2f}s, Target Frames: {frames_total}")

    # Hop length required to match target FPS
    hop_length = int(sr / args.fps)

    print("Extracting features...")
    # 1. RMS Energy (Volume) -> Mapped to 'speed' (kick)
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    
    # 2. Spectral Centroid (Brightness/Pitch) -> Mapped to 'm' and 'n'
    cent = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]

    # Make sure arrays match target frames length
    # librosa might output a few more/less frames due to windowing
    def align_length(feat, length):
        if len(feat) < length:
            return np.pad(feat, (0, length - len(feat)), mode='edge')
        return feat[:length]

    rms = align_length(rms, frames_total)
    cent = align_length(cent, frames_total)

    # Smooth features to avoid jittery visualization
    rms_smooth = smooth(rms, window_len=15)
    cent_smooth = smooth(cent, window_len=30)
    
    rms_smooth = align_length(rms_smooth, frames_total)
    cent_smooth = align_length(cent_smooth, frames_total)

    # Normalize to desired ranges for Chladni
    # Speed (Kick) ranges from 0.05 (calm) to 2.5 (explosive)
    speed_mapped = normalize(rms_smooth, 0.05, 2.5)
    
    # Chladni modes (m, n) range from 1 to 5
    # Let's map Centroid to m (1 to 5) and slightly phase-shifted Centroid to n (1 to 5)
    m_mapped = normalize(cent_smooth, 1.0, 5.0)
    # Add a slight delay to n for interesting asymmetry
    n_mapped = np.roll(m_mapped, shift=int(args.fps * 0.5))
    
    # Quantize m and n to integers or half integers for clearer patterns, 
    # but smooth transitions look better. We'll leave them continuous.

    print("Generating events...")
    events = []
    for f in range(frames_total):
        events.append({
            "frame": f,
            "m": round(float(m_mapped[f]), 3),
            "n": round(float(n_mapped[f]), 3),
            "speed": round(float(speed_mapped[f]), 4)
        })

    out_data = {
        "duration_s": duration,
        "fps": args.fps,
        "events": events
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as jf:
        json.dump(out_data, jf, indent=2)

    print(f"Done! Saved {frames_total} events to {args.output}")

if __name__ == "__main__":
    main()
