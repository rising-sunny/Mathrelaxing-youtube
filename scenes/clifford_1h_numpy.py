"""
Clifford Torus — flat torus in S³ ⊂ ℝ⁴, stereographically projected to ℝ³.

Seamless 1h horizontal (numpy particle engine):
  - Sample dense (θ, φ) grid on the Clifford torus
  - Animate 4D rotations (periodic) + in-surface phase drift
  - Camera orbits 360° in 3D after projection
  - Rainbow color by (θ, φ)
"""
import sys
import os
import math
import json
import numpy as np
from PIL import Image
import scipy.ndimage

# --------------------------------------------------------------------------
# 0. Args
# --------------------------------------------------------------------------
argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]


def arg(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default


ENGINE = str(arg("--engine", "numpy")).lower()
FRAMES = int(arg("--frames", 900))
RES_H = int(arg("--res", 1080))
FORMAT = str(arg("--format", "16:9"))
if FORMAT == "9:16":
    RES_W = int(RES_H * 9 / 16)
else:
    RES_W = int(RES_H * 16 / 9)
FPS = 60
NAME = str(arg("--name", "clifford_1h_native"))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

# --------------------------------------------------------------------------
# 1. Parameters
# --------------------------------------------------------------------------
# Grid density on T² (θ × φ)
N_THETA = 180
N_PHI = 160
N = N_THETA * N_PHI  # 28_800 particles
TRAIL = 48

# Clifford radii on S³: r1² + r2² = 1  (classic equal: 1/√2)
R1 = 1.0 / math.sqrt(2.0)
R2 = 1.0 / math.sqrt(2.0)

# 4D rotation speeds (full turns over the loop → seamless)
# Planes: xy, zw, xw, yz
TURNS_XY = 1.0
TURNS_ZW = 1.0
TURNS_XW = 0.0   # keep identity contribution optional
TURNS_YZ = 1.0

# In-surface phase drift (particles slide on the torus)
TURNS_THETA = 1.0
TURNS_PHI = 1.0


def hsv_to_rgb(h, s, v):
    h = np.asarray(h)
    s = np.asarray(s)
    v = np.asarray(v)
    i = np.floor(h * 6.0).astype(int) % 6
    f = h * 6.0 - np.floor(h * 6.0)
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)


def seed_torus():
    """(θ0, φ0) grid + colors."""
    th = np.linspace(0, 2 * np.pi, N_THETA, endpoint=False)
    ph = np.linspace(0, 2 * np.pi, N_PHI, endpoint=False)
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    theta0 = TH.ravel().astype(np.float64)
    phi0 = PH.ravel().astype(np.float64)

    # Hue from θ, secondary from φ
    hue = (theta0 / (2 * np.pi) + 0.15 * phi0 / (2 * np.pi)) % 1.0
    sat = 0.72 + 0.28 * np.sin(phi0) ** 2
    val = 0.55 + 0.45 * (0.5 + 0.5 * np.cos(theta0))
    colors = hsv_to_rgb(hue, sat, val).astype(np.float32)
    return theta0, phi0, colors


def clifford_s3(theta, phi):
    """Clifford torus points in ℝ⁴ ⊂ S³."""
    x = R1 * np.cos(theta)
    y = R1 * np.sin(theta)
    z = R2 * np.cos(phi)
    w = R2 * np.sin(phi)
    return x, y, z, w


def rot_plane(a, b, ang):
    """Rotate coordinates (a,b) by ang (vectorized)."""
    c, s = np.cos(ang), np.sin(ang)
    return c * a - s * b, s * a + c * b


def apply_4d_rotations(x, y, z, w, frame):
    """Periodic SO(4)-style plane rotations."""
    p = frame / FRAMES
    a_xy = 2 * np.pi * TURNS_XY * p
    a_zw = 2 * np.pi * TURNS_ZW * p
    a_xw = 2 * np.pi * TURNS_XW * p
    a_yz = 2 * np.pi * TURNS_YZ * p

    x, y = rot_plane(x, y, a_xy)
    z, w = rot_plane(z, w, a_zw)
    x, w = rot_plane(x, w, a_xw)
    y, z = rot_plane(y, z, a_yz)
    return x, y, z, w


def stereo_project(x, y, z, w):
    """Stereographic S³ → ℝ³ from south pole w = -1."""
    denom = np.maximum(1.0 + w, 1e-4)
    X = x / denom
    Y = y / denom
    Z = z / denom
    return np.stack([X, Y, Z], axis=-1)


def positions_at(theta0, phi0, frame):
    p = frame / FRAMES
    theta = theta0 + 2 * np.pi * TURNS_THETA * p
    phi = phi0 + 2 * np.pi * TURNS_PHI * p
    x, y, z, w = clifford_s3(theta, phi)
    x, y, z, w = apply_4d_rotations(x, y, z, w, frame)
    return stereo_project(x, y, z, w).astype(np.float32)


def positions_trail(theta0, phi0, frame):
    offs = np.arange(-(TRAIL - 1), 1, dtype=np.float64)
    frames = (frame + offs) % FRAMES
    # Vectorize over trail: compute each step (trail is small)
    hist = np.zeros((TRAIL, N, 3), dtype=np.float32)
    for i, ff in enumerate(frames):
        hist[i] = positions_at(theta0, phi0, int(ff))
    return hist


# --------------------------------------------------------------------------
# 2. Events
# --------------------------------------------------------------------------
def build_events(rng):
    events = []
    for f in range(40, FRAMES, 40):
        phase = 2.0 * math.pi * f / FRAMES
        intensity = 0.5 + 0.4 * abs(math.sin(phase * 2.0))
        note = str(rng.choice(["C3", "E3", "G3", "B3", "D4", "A3"]))
        events.append({
            "frame": f,
            "t_seconds": round(f / FPS, 4),
            "type": "torus_pulse",
            "intensity": float(intensity),
            "note": note,
        })
    return events


# --------------------------------------------------------------------------
# 3. Camera + render
# --------------------------------------------------------------------------
def cam_matrix(f):
    progress = f / max(1, FRAMES)
    theta = math.radians(20) + math.radians(360) * progress
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    Rz = np.array([
        [cos_t, -sin_t, 0],
        [sin_t, cos_t, 0],
        [0, 0, 1],
    ], dtype=np.float64)
    phi = math.radians(28) + math.radians(10) * math.sin(progress * 2 * math.pi)
    cos_p, sin_p = np.cos(phi), np.sin(phi)
    Rx = np.array([
        [1, 0, 0],
        [0, cos_p, -sin_p],
        [0, sin_p, cos_p],
    ], dtype=np.float64)
    return Rz @ Rx


def render_history(history, R, PROJ_SCALE, colors):
    img = np.zeros((RES_H, RES_W, 3), dtype=np.float32)
    history_rot = history @ R.T

    X_screen = (history_rot[:, :, 0] * PROJ_SCALE + RES_W / 2).astype(int)
    Y_screen = (-history_rot[:, :, 2] * PROJ_SCALE + RES_H / 2).astype(int)

    for t in range(TRAIL):
        alpha = ((t + 1) / TRAIL) ** 1.25
        alpha *= 0.022

        xs = X_screen[t]
        ys = Y_screen[t]
        valid = (xs >= 0) & (xs < RES_W) & (ys >= 0) & (ys < RES_H)
        xs_v, ys_v = xs[valid], ys[valid]
        c_v = colors[valid]

        np.add.at(img[:, :, 0], (ys_v, xs_v), c_v[:, 0] * alpha)
        np.add.at(img[:, :, 1], (ys_v, xs_v), c_v[:, 1] * alpha)
        np.add.at(img[:, :, 2], (ys_v, xs_v), c_v[:, 2] * alpha)

    return img


def run():
    rng = np.random.default_rng(42)
    print(f"[clifford] Sembrando {N} puntos en el toro de Clifford (S³)...")
    theta0, phi0, colors = seed_torus()

    events = build_events(rng)
    with open(EVENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "fps": FPS,
            "frames": FRAMES,
            "duration_s": round(FRAMES / FPS, 4),
            "resolution": [RES_W, RES_H],
            "engine": ENGINE,
            "system": "clifford_torus",
            "events": events,
        }, fh, indent=2, ensure_ascii=False)
    print(f"[clifford] Eventos: {len(events)} -> {EVENTS_PATH}")

    # Stereographic Clifford typically lives in a ball of radius ~2–3
    PROJ_SCALE = 280.0 if FORMAT == "16:9" else 320.0

    print(f"[clifford] Renderizando {FRAMES} frames SEAMLESS (4D + stereo)...")
    for f in range(FRAMES):
        out_path = os.path.join(FRAMES_DIR, f"{f:04d}.png")
        if os.path.exists(out_path):
            continue

        R = cam_matrix(f)
        hist = positions_trail(theta0, phi0, f)
        img = render_history(hist, R, PROJ_SCALE, colors)

        bloom = scipy.ndimage.gaussian_filter(img, sigma=4.0)
        img = img * 1.35 + bloom * 1.05
        bloom2 = scipy.ndimage.gaussian_filter(img, sigma=10.0)
        img = img + bloom2 * 0.22
        img = np.power(np.clip(img, 0, 1), 0.9)

        img = np.clip(img, 0, 1)
        Image.fromarray((img * 255).astype(np.uint8)).save(out_path)

        if f % 24 == 0 or f == FRAMES - 1:
            print(f"[clifford] frame {f + 1}/{FRAMES}")

    print("\n[clifford] ====== RESUMEN ======")
    print(f"[clifford] motor   : {ENGINE} ({RES_W}x{RES_H})")
    print(f"[clifford] frames  : {FRAMES} -> {FRAMES_DIR}")


if __name__ == "__main__":
    run()
