"""
Three-Body Problem — Moore Figure-8 Choreography.

Equal masses on the famous periodic figure-8 orbit (Chenciner–Montgomery).

Modes:
  16:9 (1h)  — slow dense tubes, gentle orbit
  9:16 short — multi-period race, cinematic camera, bright cores, cross flashes
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
NAME = str(arg("--name", "threebody_1h_native"))

# Short mode = vertical + explicit flag (or 9:16)
SHORT_MODE = FORMAT == "9:16" or str(arg("--short", "0")) in ("1", "true", "yes")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

# --------------------------------------------------------------------------
# 1. Physics — Moore figure-8
# --------------------------------------------------------------------------
G = 1.0
M = np.array([1.0, 1.0, 1.0], dtype=np.float64)

P0 = np.array([
    [0.97000436, -0.24308753, 0.0],
    [-0.97000436, 0.24308753, 0.0],
    [0.0, 0.0, 0.0],
], dtype=np.float64)

V0 = np.array([
    [0.4662036850, 0.4323657300, 0.0],
    [0.4662036850, 0.4323657300, 0.0],
    [-0.93240737, -0.86473146, 0.0],
], dtype=np.float64)

T_PERIOD = 6.32591398

# Visual density / motion
if SHORT_MODE:
    N_PER_BODY = 5500
    TRAIL = 100
    ORBIT_LOOPS = 5          # 5 vueltas del ∞ en el clip → mucho más movimiento
    Z_SPREAD = 0.04
    BODY_Z_GAP = 0.07
    HEAD_TRAIL = 140         # cola extra de los 3 núcleos
else:
    N_PER_BODY = 7000
    TRAIL = 55
    ORBIT_LOOPS = 1
    Z_SPREAD = 0.035
    BODY_Z_GAP = 0.055
    HEAD_TRAIL = 40

N = N_PER_BODY * 3

BODY_COLORS = np.array([
    [0.10, 0.95, 1.00],   # cyan
    [1.00, 0.18, 0.88],   # magenta
    [1.00, 0.82, 0.10],   # gold
], dtype=np.float32)


def accelerations(pos):
    acc = np.zeros_like(pos)
    for i in range(3):
        for j in range(i + 1, 3):
            r = pos[j] - pos[i]
            d2 = float(np.dot(r, r)) + 1e-12
            d = math.sqrt(d2)
            f = G * M[i] * M[j] / (d2 * d)
            acc[i] += f * r / M[i]
            acc[j] -= f * r / M[j]
    return acc


def rk4_step(pos, vel, dt):
    a1 = accelerations(pos)
    k1v, k1x = a1, vel
    a2 = accelerations(pos + 0.5 * dt * k1x)
    k2v, k2x = a2, vel + 0.5 * dt * k1v
    a3 = accelerations(pos + 0.5 * dt * k2x)
    k3v, k3x = a3, vel + 0.5 * dt * k2v
    a4 = accelerations(pos + dt * k3x)
    k4v, k4x = a4, vel + dt * k3v
    pos_n = pos + (dt / 6.0) * (k1x + 2 * k2x + 2 * k3x + k4x)
    vel_n = vel + (dt / 6.0) * (k1v + 2 * k2v + 2 * k3v + k4v)
    return pos_n, vel_n


def integrate_period(n_samples):
    sub = 8
    dt = T_PERIOD / (n_samples * sub)
    pos = P0.copy()
    vel = V0.copy()
    orbit = np.zeros((n_samples, 3, 3), dtype=np.float64)
    for s in range(n_samples):
        orbit[s] = pos
        for _ in range(sub):
            pos, vel = rk4_step(pos, vel, dt)
    drift = float(np.linalg.norm(orbit[0] - pos))
    print(f"[threebody] period close drift: {drift:.6e}")
    return orbit.astype(np.float32)


def seed_particles(rng):
    body_id = np.repeat(np.arange(3), N_PER_BODY)
    phase = np.tile(np.arange(N_PER_BODY), 3).astype(np.float64)
    phase = (phase / N_PER_BODY * 1.0)  # [0,1) fraction of orbit
    # Convert later to sample index

    jitter = rng.normal(0.0, 0.012, size=(N, 3)).astype(np.float32)
    jitter[:, 2] = rng.normal(0.0, Z_SPREAD, size=N).astype(np.float32)
    jitter[:, 2] += ((body_id - 1).astype(np.float32) * BODY_Z_GAP)

    colors = BODY_COLORS[body_id].copy()
    shade = 0.80 + 0.20 * rng.random(N).astype(np.float32)
    colors *= shade[:, None]
    return body_id, phase.astype(np.float32), jitter, colors.astype(np.float32)


def orbit_index(phase_frac, frame, n_orb):
    """phase_frac in [0,1), advances ORBIT_LOOPS full periods over FRAMES."""
    # (phase + loops * frame/FRAMES) mod 1 → sample
    t = (phase_frac + ORBIT_LOOPS * (frame / FRAMES)) % 1.0
    return (t * n_orb).astype(np.int32) % n_orb


def positions_at(orbit, body_id, phase, jitter, frame):
    n_orb = orbit.shape[0]
    idx = orbit_index(phase, frame, n_orb)
    base = orbit[idx, body_id]
    return (base + jitter).astype(np.float32)


def positions_trail(orbit, body_id, phase, jitter, frame, trail_len):
    n_orb = orbit.shape[0]
    offs = np.arange(-(trail_len - 1), 1, dtype=np.float64)
    frames = (frame + offs) % FRAMES
    # (T, N)
    t = (phase[None, :] + ORBIT_LOOPS * (frames[:, None] / FRAMES)) % 1.0
    idx = (t * n_orb).astype(np.int32) % n_orb
    base = orbit[idx, body_id[None, :]]
    return (base + jitter[None, :, :]).astype(np.float32)


def body_heads_trail(orbit, frame, trail_len):
    """(T, 3, 3) positions of the 3 actual bodies over trail history."""
    n_orb = orbit.shape[0]
    offs = np.arange(-(trail_len - 1), 1, dtype=np.float64)
    frames = (frame + offs) % FRAMES
    # Body b is phase-offset by b/3 along the choreography
    # Actually each body has fixed phase offset of T/3 on the shared curve
    # From integration: body 0,1,2 at sample s are the 3 positions at that time
    t = (ORBIT_LOOPS * (frames / FRAMES)) % 1.0
    idx = (t * n_orb).astype(np.int32) % n_orb
    # (T, 3, 3)
    return orbit[idx]  # advanced: orbit[idx[i]] → (3,3) per t


def pairwise_min_dist(orbit, frame):
    """Min distance among 3 bodies at this frame (for flash intensity)."""
    n_orb = orbit.shape[0]
    t = (ORBIT_LOOPS * (frame / FRAMES)) % 1.0
    idx = int(t * n_orb) % n_orb
    p = orbit[idx]
    d01 = float(np.linalg.norm(p[0] - p[1]))
    d02 = float(np.linalg.norm(p[0] - p[2]))
    d12 = float(np.linalg.norm(p[1] - p[2]))
    return min(d01, d02, d12)


# --------------------------------------------------------------------------
# 2. Events
# --------------------------------------------------------------------------
def build_events(rng, orbit):
    events = []
    # Pulses denser in short mode; also near close approaches
    step = 18 if SHORT_MODE else 40
    for f in range(step, FRAMES, step):
        dmin = pairwise_min_dist(orbit, f)
        # closer → louder
        closeness = float(np.clip(1.2 - dmin, 0.2, 1.2))
        note = str(rng.choice(["C3", "E3", "G3", "A3", "D4", "B3", "F4"]))
        events.append({
            "frame": f,
            "t_seconds": round(f / FPS, 4),
            "type": "orbit_pulse",
            "intensity": closeness,
            "note": note,
            "dmin": round(dmin, 4),
        })
    return events


# --------------------------------------------------------------------------
# 3. Camera — fixed elevation + azimuth spin (never edge-on)
# --------------------------------------------------------------------------
def cam_matrix(f):
    progress = f / max(1, FRAMES)
    if SHORT_MODE:
        # Azimuth: full turn; slight secondary wobble for life
        azim = math.radians(-40) + math.radians(360) * progress
        # Elevation from horizontal: fixed ~48° + gentle breathe (seamless)
        elev = math.radians(48) + math.radians(7) * math.sin(progress * 2 * math.pi)
        # Optional roll for drama
        roll = math.radians(6) * math.sin(progress * 2 * math.pi)
    else:
        azim = math.radians(-30) + math.radians(360) * progress
        elev = math.radians(58) + math.radians(8) * math.sin(progress * 2 * math.pi)
        roll = 0.0

    ca, sa = np.cos(azim), np.sin(azim)
    ce, se = np.cos(elev), np.sin(elev)
    cr, sr = np.cos(roll), np.sin(roll)

    # Rz(azim) then Rx(elev) then Rz(roll) — elev keeps foreshortening constant-ish
    Rz_a = np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]], dtype=np.float64)
    Rx_e = np.array([[1, 0, 0], [0, ce, -se], [0, se, ce]], dtype=np.float64)
    Rz_r = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]], dtype=np.float64)
    return Rz_r @ Rx_e @ Rz_a


def proj_scale_for_frame(f):
    progress = f / max(1, FRAMES)
    if SHORT_MODE:
        base = min(RES_W, RES_H) * 0.40
        # Zoom breathe seamless (1 cycle)
        return base * (1.0 + 0.12 * math.sin(progress * 2 * math.pi))
    if FORMAT == "9:16":
        return min(RES_W, RES_H) * 0.38
    return 380.0


def project(pts, R, scale, cx, cy):
    """pts (..., 3) → xs, ys int arrays same leading shape."""
    rot = pts @ R.T
    xs = (rot[..., 0] * scale + cx)
    # After elev Rx, y maps partly to z — use z for vertical screen (depth tilt)
    ys = (-rot[..., 2] * scale + cy)
    return xs, ys


def splat_add(img, xs, ys, colors, alpha, radius=0):
    """Add particles; radius>0 draws a small disc for heads."""
    H, W = img.shape[:2]
    if radius <= 0:
        xi = xs.astype(np.int32)
        yi = ys.astype(np.int32)
        valid = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
        if colors.ndim == 1:
            # single color broadcast
            for c in range(3):
                np.add.at(img[:, :, c], (yi[valid], xi[valid]), colors[c] * alpha)
        else:
            for c in range(3):
                np.add.at(img[:, :, c], (yi[valid], xi[valid]), colors[valid, c] * alpha)
        return

    # Soft disc for bright heads
    offs = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius:
                fall = 1.0 - math.sqrt(dx * dx + dy * dy) / (radius + 0.5)
                offs.append((dx, dy, fall ** 1.5))

    xi0 = xs.astype(np.int32)
    yi0 = ys.astype(np.int32)
    n = xi0.shape[0]
    for dx, dy, fall in offs:
        xi = xi0 + dx
        yi = yi0 + dy
        valid = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
        a = alpha * fall
        if colors.ndim == 1:
            for c in range(3):
                np.add.at(img[:, :, c], (yi[valid], xi[valid]), colors[c] * a)
        else:
            for c in range(3):
                np.add.at(img[:, :, c], (yi[valid], xi[valid]), colors[valid, c] * a)


def render_frame(orbit, body_id, phase, jitter, colors, f, R, scale):
    img = np.zeros((RES_H, RES_W, 3), dtype=np.float32)
    cx, cy = RES_W / 2.0, RES_H / 2.0

    # --- Ghost tubes (dense path) ---
    hist = positions_trail(orbit, body_id, phase, jitter, f, TRAIL)
    # (T, N, 3)
    for t in range(TRAIL):
        alpha = ((t + 1) / TRAIL) ** 1.5
        alpha *= 0.022 if SHORT_MODE else 0.018
        xs, ys = project(hist[t], R, scale, cx, cy)
        splat_add(img, xs, ys, colors, alpha, radius=0)

    if SHORT_MODE:
        # --- Bright body cores + long colored streaks ---
        heads = body_heads_trail(orbit, f, HEAD_TRAIL)  # (T, 3, 3)
        for t in range(HEAD_TRAIL):
            fade = ((t + 1) / HEAD_TRAIL) ** 1.2
            # trail particles: thin
            for b in range(3):
                p = heads[t, b][None, :]
                xs, ys = project(p, R, scale, cx, cy)
                splat_add(img, xs, ys, BODY_COLORS[b], 0.08 * fade, radius=1)

        # current heads — big soft discs
        p_now = heads[-1]  # (3, 3)
        xs, ys = project(p_now, R, scale, cx, cy)
        for b in range(3):
            splat_add(img, xs[b:b+1], ys[b:b+1], BODY_COLORS[b], 1.4, radius=5)
            # white hot core
            splat_add(img, xs[b:b+1], ys[b:b+1], np.array([1.0, 1.0, 1.0]), 0.9, radius=2)

        # Close-approach flash (global lift)
        dmin = pairwise_min_dist(orbit, f)
        if dmin < 0.85:
            flash = (0.85 - dmin) / 0.85
            img += flash * 0.18 * img  # boost existing light
            # radial bloom proxy: add soft white at COM
            com = p_now.mean(axis=0, keepdims=True)
            xs, ys = project(com, R, scale, cx, cy)
            splat_add(img, xs, ys, np.array([1.0, 0.95, 1.0]), 0.35 * flash, radius=18)

    return img


def run():
    rng = np.random.default_rng(42)
    n_orb = max(FRAMES * 3, 2400)
    mode = "SHORT-dynamic" if SHORT_MODE else "1h"
    print(f"[threebody] mode={mode} loops={ORBIT_LOOPS} trail={TRAIL}")
    print(f"[threebody] Integrando órbita figure-8 ({n_orb} samples)...")
    orbit = integrate_period(n_orb)

    print(f"[threebody] Sembrando {N} partículas ({N_PER_BODY}/cuerpo)...")
    body_id, phase, jitter, colors = seed_particles(rng)

    events = build_events(rng, orbit)
    with open(EVENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "fps": FPS,
            "frames": FRAMES,
            "duration_s": round(FRAMES / FPS, 4),
            "resolution": [RES_W, RES_H],
            "engine": ENGINE,
            "system": "three_body_figure8",
            "period": T_PERIOD,
            "orbit_loops": ORBIT_LOOPS,
            "short_mode": SHORT_MODE,
            "events": events,
        }, fh, indent=2, ensure_ascii=False)
    print(f"[threebody] Eventos: {len(events)} -> {EVENTS_PATH}")

    print(f"[threebody] Renderizando {FRAMES} frames SEAMLESS...")
    for f in range(FRAMES):
        out_path = os.path.join(FRAMES_DIR, f"{f:04d}.png")
        if os.path.exists(out_path):
            continue

        R = cam_matrix(f)
        scale = proj_scale_for_frame(f)
        img = render_frame(orbit, body_id, phase, jitter, colors, f, R, scale)

        # Bloom — stronger in short mode for cinematic punch
        if SHORT_MODE:
            bloom = scipy.ndimage.gaussian_filter(img, sigma=3.0)
            img = img * 1.15 + bloom * 0.85
            bloom2 = scipy.ndimage.gaussian_filter(img, sigma=9.0)
            img = img + bloom2 * 0.28
            # slight contrast curve
            img = np.power(np.clip(img, 0, 1), 0.92)
        else:
            bloom = scipy.ndimage.gaussian_filter(img, sigma=3.5)
            img = img * 1.25 + bloom * 0.65
            bloom2 = scipy.ndimage.gaussian_filter(img, sigma=8.0)
            img = img + bloom2 * 0.15

        img = np.clip(img, 0, 1)
        Image.fromarray((img * 255).astype(np.uint8)).save(out_path)

        if f % 24 == 0 or f == FRAMES - 1:
            print(f"[threebody] frame {f + 1}/{FRAMES}")

    print("\n[threebody] ====== RESUMEN ======")
    print(f"[threebody] motor   : {ENGINE} ({RES_W}x{RES_H}) mode={mode}")
    print(f"[threebody] frames  : {FRAMES} -> {FRAMES_DIR}")


if __name__ == "__main__":
    run()
