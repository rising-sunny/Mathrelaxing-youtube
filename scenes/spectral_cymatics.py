"""
spectral_cymatics.py — Cymatics espectral 9:16 (sin Blender).

Analiza una pista WAV (RMS + bandas de frecuencia) y genera un campo de
interferencia polar (ondas estacionarias) con colormap neón + glow.
Ideal para Shorts con música externa.

    python scenes/spectral_cymatics.py \
        --audio "path/to/track.wav" \
        --name shorts_spectral \
        --duration 30 --fps 30 \
        --width 576 --height 1024
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy.io import wavfile
from scipy.ndimage import gaussian_filter1d

# ==============================================================================
# Colormap + glow
# ==============================================================================

def make_colormap():
    """Negro → índigo → magenta → cian → blanco cálido."""
    n = 256
    cmap = np.zeros((n, 3), dtype=np.uint8)
    stops = [
        (0.00, (0, 0, 8)),
        (0.15, (18, 4, 48)),
        (0.35, (90, 12, 120)),
        (0.55, (20, 80, 200)),
        (0.75, (40, 220, 210)),
        (0.90, (200, 240, 180)),
        (1.00, (255, 250, 240)),
    ]
    for i in range(n):
        t = i / (n - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                s = (t - t0) / (t1 - t0 + 1e-12)
                cmap[i] = [
                    int(c0[0] + (c1[0] - c0[0]) * s),
                    int(c0[1] + (c1[1] - c0[1]) * s),
                    int(c0[2] + (c1[2] - c0[2]) * s),
                ]
                break
    return cmap


def apply_glow(img: Image.Image, radius=5, intensity=0.42) -> Image.Image:
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    return Image.blend(img, blurred, intensity)


# ==============================================================================
# Audio analysis (scipy + numpy, sin librosa)
# ==============================================================================

def load_mono(path: str):
    sr, data = wavfile.read(path)
    if data.ndim > 1:
        y = data.astype(np.float64).mean(axis=1)
    else:
        y = data.astype(np.float64)
    peak = np.max(np.abs(y)) or 1.0
    y /= peak
    return y, int(sr)


def analyze_audio(y: np.ndarray, sr: int, fps: int, start_s: float, duration_s: float):
    """Por cada frame: RMS, centroide, 6 bandas de energía, onset proxy."""
    n0 = int(start_s * sr)
    n1 = int((start_s + duration_s) * sr)
    y = y[n0:n1]
    n_frames = int(round(duration_s * fps))
    hop = max(1, int(sr / fps))
    win = max(hop * 2, 1024)
    if win % 2:
        win += 1

    # Band edges (Hz) — graves → agudos
    band_edges = [40, 120, 300, 800, 2000, 5000, 12000]
    n_bands = len(band_edges) - 1

    rms = np.zeros(n_frames)
    centroid = np.zeros(n_frames)
    bands = np.zeros((n_frames, n_bands))
    freqs = np.fft.rfftfreq(win, d=1.0 / sr)

    for f in range(n_frames):
        c = f * hop
        a = max(0, c - win // 2)
        b = min(len(y), a + win)
        chunk = np.zeros(win)
        take = b - a
        if take > 0:
            chunk[:take] = y[a:b]
        if take < win:
            # pad end with silence
            pass
        windowed = chunk * np.hanning(win)
        spec = np.abs(np.fft.rfft(windowed))
        power = spec ** 2
        psum = power.sum() + 1e-12

        rms[f] = float(np.sqrt(np.mean(chunk ** 2)))
        centroid[f] = float((freqs * power).sum() / psum)

        for bi in range(n_bands):
            lo, hi = band_edges[bi], band_edges[bi + 1]
            mask = (freqs >= lo) & (freqs < hi)
            bands[f, bi] = float(power[mask].sum() / psum)

    # Suavizado temporal
    rms = gaussian_filter1d(rms, sigma=2.0)
    centroid = gaussian_filter1d(centroid, sigma=4.0)
    for bi in range(n_bands):
        bands[:, bi] = gaussian_filter1d(bands[:, bi], sigma=3.0)

    # Normalizar
    def norm01(x):
        lo, hi = float(np.percentile(x, 5)), float(np.percentile(x, 95))
        return np.clip((x - lo) / (hi - lo + 1e-9), 0.0, 1.0)

    rms_n = norm01(rms)
    cent_n = norm01(centroid)
    bands_n = np.stack([norm01(bands[:, bi]) for bi in range(n_bands)], axis=1)

    # Onset proxy: subida de RMS
    onset = np.clip(np.diff(rms_n, prepend=rms_n[0]), 0, None)
    onset = gaussian_filter1d(onset, sigma=1.0)
    onset = norm01(onset)

    return {
        "rms": rms_n,
        "centroid": cent_n,
        "bands": bands_n,
        "onset": onset,
        "n_frames": n_frames,
    }


# ==============================================================================
# Campo cymatics polar
# ==============================================================================

def build_grid(grid_w: int, grid_h: int):
    """Coordenadas normalizadas centradas; r en [0, ~1], theta en [-pi, pi]."""
    ys = np.linspace(-1.0, 1.0, grid_h)
    xs = np.linspace(-1.0 * grid_w / grid_h, 1.0 * grid_w / grid_h, grid_w)
    X, Y = np.meshgrid(xs, ys)
    R = np.sqrt(X ** 2 + Y ** 2) + 1e-6
    TH = np.arctan2(Y, X)
    return R, TH


def field_frame(R, TH, t, rms, cent, bands, onset, phase_accum):
    """
    Superposición de modos polares:
      cos(k r - ω t) * cos(m θ + φ)
    impulsados por bandas de audio.
    """
    # Amplitudes por banda
    a = 0.15 + 0.85 * bands  # (6,)
    # Radios de onda y armónicos angulares
    ks = np.array([6.0, 10.0, 15.0, 22.0, 32.0, 45.0]) * (0.85 + 0.45 * cent)
    ms = np.array([2, 3, 4, 5, 7, 9])
    omegas = np.array([0.8, 1.1, 1.4, 1.8, 2.3, 2.9]) * (0.7 + 0.8 * rms)

    phase_accum += omegas * (1.0 / 30.0)  # avanza fase (se escala fuera con fps real)
    # Caller passes dphase separately — see render loop.

    field = np.zeros_like(R)
    for i in range(len(ks)):
        phi = phase_accum[i] + onset * 0.8 * (i + 1)
        radial = np.cos(ks[i] * R - phi)
        angular = np.cos(ms[i] * TH + 0.35 * i + cent * np.pi)
        # Envelope radial suave (más brillo al centro en beats)
        env = np.exp(-R * (1.2 - 0.5 * rms))
        field += a[i] * radial * angular * env

    # Anillo de energía (onset)
    ring = np.exp(-((R - (0.25 + 0.45 * rms)) ** 2) / (0.04 + 0.06 * onset + 1e-6))
    field += (0.35 + 0.9 * onset) * ring * np.cos(18 * TH + phase_accum[0])

    # Normalizar suave
    field = field / (1.5 + rms)
    return field, phase_accum


def to_rgb(field, cmap, rms, onset):
    # Mapear campo a [0,1] con contraste dinámico
    lo = np.percentile(field, 8)
    hi = np.percentile(field, 99)
    n = np.clip((field - lo) / (hi - lo + 1e-9), 0, 1)
    # Empujar brillo con RMS
    n = np.clip(n ** (0.85 - 0.25 * rms) + 0.08 * onset, 0, 1)
    idx = (n * 255).astype(np.uint8)
    return cmap[idx]


# ==============================================================================
# Main render
# ==============================================================================

def render(
    audio_path: str,
    name: str,
    start_s: float = 0.0,
    duration_s: float = 30.0,
    fps: int = 30,
    grid_w: int = 288,
    out_w: int = 576,
    out_h: int = 1024,
):
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(repo, "output", name, "frames")
    os.makedirs(outdir, exist_ok=True)
    events_path = os.path.join(repo, "data", f"{name}_events.json")

    # Dimensiones pares (H.264)
    out_w = max(2, (out_w // 2) * 2)
    out_h = max(2, (out_h // 2) * 2)

    print(f"[spectral] Cargando audio: {audio_path}")
    y, sr = load_mono(audio_path)
    full_dur = len(y) / sr
    if start_s + duration_s > full_dur:
        duration_s = max(1.0, full_dur - start_s)
        print(f"[spectral] Ajustando duration a {duration_s:.2f}s (fin de pista)")

    print(f"[spectral] Analizando {duration_s:.1f}s @ {fps} fps (start={start_s:.1f}s)...")
    feat = analyze_audio(y, sr, fps, start_s, duration_s)
    n_frames = feat["n_frames"]

    print(f"[spectral] Grid {grid_w}x{int(grid_w * out_h / out_w)} → {out_w}x{out_h}")
    grid_h = max(8, int(round(grid_w * out_h / out_w)))
    R, TH = build_grid(grid_w, grid_h)
    cmap = make_colormap()

    phase = np.zeros(6, dtype=np.float64)
    dt_phase = 1.0 / fps
    events = []

    print(f"[spectral] Renderizando {n_frames} frames...")
    for f in range(n_frames):
        rms = float(feat["rms"][f])
        cent = float(feat["centroid"][f])
        bands = feat["bands"][f]
        onset = float(feat["onset"][f])

        # Avance de fase proporcional a energía (más movimiento en crescendos)
        omegas = np.array([0.8, 1.1, 1.4, 1.8, 2.3, 2.9]) * (0.6 + 1.2 * rms)
        phase = phase + omegas * dt_phase * (1.0 + 0.5 * onset)

        field = np.zeros_like(R)
        ks = np.array([6.0, 10.0, 15.0, 22.0, 32.0, 45.0]) * (0.85 + 0.5 * cent)
        ms = np.array([2, 3, 4, 5, 7, 9])
        for i in range(6):
            a = 0.12 + 0.88 * float(bands[i])
            radial = np.cos(ks[i] * R - phase[i])
            angular = np.cos(ms[i] * TH + 0.4 * i + cent * np.pi)
            env = np.exp(-R * (1.35 - 0.55 * rms))
            field += a * radial * angular * env

        ring_r = 0.2 + 0.5 * rms
        ring = np.exp(-((R - ring_r) ** 2) / (0.035 + 0.07 * onset + 1e-6))
        field += (0.3 + 1.0 * onset) * ring * np.cos(16 * TH + phase[0] * 1.3)
        field /= 1.4 + 0.6 * rms

        rgb = to_rgb(field, cmap, rms, onset)
        img = Image.fromarray(rgb, mode="RGB")
        canvas = img.resize((out_w, out_h), Image.LANCZOS)
        # Glow más fuerte en onsets
        glow_r = 4 + int(3 * onset)
        canvas = apply_glow(canvas, radius=glow_r, intensity=0.35 + 0.25 * rms)
        canvas.save(os.path.join(outdir, f"{f:04d}.png"))

        events.append({
            "frame": f,
            "t_seconds": round(f / fps, 4),
            "rms": round(rms, 4),
            "centroid": round(cent, 4),
            "onset": round(onset, 4),
            "bands": [round(float(b), 4) for b in bands],
        })

        if f % 30 == 0 or f == n_frames - 1:
            print(f"[spectral] frame {f + 1}/{n_frames}  rms={rms:.2f} onset={onset:.2f}")

    with open(events_path, "w", encoding="utf-8") as fh:
        json.dump({
            "fps": fps,
            "frames": n_frames,
            "duration_s": round(n_frames / fps, 4),
            "resolution": [out_w, out_h],
            "audio": os.path.abspath(audio_path),
            "audio_start_s": start_s,
            "engine": "numpy",
            "events": events,
        }, fh, indent=2)

    print(f"[spectral] Events → {events_path}")
    print(f"[spectral] DONE → {outdir}")
    return n_frames, out_w, out_h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--name", default="shorts_spectral")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--grid", type=int, default=288)
    ap.add_argument("--width", type=int, default=576)
    ap.add_argument("--height", type=int, default=1024)
    # Compat con build_clip si se invoca con -- residual
    ap.add_argument("--engine", default="numpy")
    ap.add_argument("--frames", type=int, default=None)
    ap.add_argument("--res", type=int, default=None)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--format", default="9:16")
    a = ap.parse_args()

    # Permitir argv de Blender-style: script -- --flags
    if "--" in sys.argv:
        pass  # argparse ya parseó sys.argv completo o no; ok

    if a.res:
        a.height = a.res
        a.width = max(2, (int(a.res * 9 / 16) // 2) * 2)

    render(
        audio_path=a.audio,
        name=a.name,
        start_s=a.start,
        duration_s=a.duration,
        fps=a.fps,
        grid_w=a.grid,
        out_w=a.width,
        out_h=a.height,
    )


if __name__ == "__main__":
    main()
