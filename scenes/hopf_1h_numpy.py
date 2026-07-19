"""
Hopf Fibration — 1h seamless horizontal (numpy particle engine).

Particles ride the circular S¹ fibers of the Hopf map S³ → S², stereographically
projected into R³. Motion is exactly 2π-periodic → perfect loop without
temporal crossfade blend.
"""
import sys
import os
import math
import json
import numpy as np
from PIL import Image
import scipy.ndimage

# --------------------------------------------------------------------------
# 0. Argumentos
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
NAME = str(arg("--name", "hopf_1h_native"))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

# --------------------------------------------------------------------------
# 1. Parámetros
# --------------------------------------------------------------------------
N = 28000            # partículas
TRAIL = 55           # cola a lo largo de la fibra
N_FIBERS = 700       # fibras base en S²
# partículas por fibra (aprox)
PER_FIBER = max(1, N // N_FIBERS)

# Evitar el polo de proyección estereográfica (w → -1)
ZETA_MIN = 0.12
ZETA_MAX = math.pi - 0.12


def hopf_s3(zeta, eta, xi):
    """Punto en S³ ⊂ ℂ² ≅ ℝ⁴ (coordenadas de Hopf)."""
    half_z = 0.5 * zeta
    c_z = np.cos(half_z)
    s_z = np.sin(half_z)
    a = 0.5 * (xi + eta)
    b = 0.5 * (xi - eta)
    z1_re = c_z * np.cos(a)
    z1_im = c_z * np.sin(a)
    z2_re = s_z * np.cos(b)
    z2_im = s_z * np.sin(b)
    return z1_re, z1_im, z2_re, z2_im


def stereo_project(z1_re, z1_im, z2_re, z2_im):
    """Proyección estereográfica S³ → ℝ³ desde el polo sur (w = -1)."""
    # ℝ⁴ = (x, y, z, w) = (z1_re, z1_im, z2_re, z2_im)
    denom = 1.0 + z2_im
    denom = np.maximum(denom, 1e-4)
    X = z1_re / denom
    Y = z1_im / denom
    Z = z2_re / denom
    return np.stack([X, Y, Z], axis=-1)


def positions_at(zeta, eta, xi0, frame):
    """Posiciones 3D de todas las partículas en el frame dado (periódico)."""
    xi = xi0 + (2.0 * math.pi) * (frame / FRAMES)
    z1_re, z1_im, z2_re, z2_im = hopf_s3(zeta, eta, xi)
    return stereo_project(z1_re, z1_im, z2_re, z2_im)


def positions_trail(zeta, eta, xi0, frame):
    """Cola modular (TRAIL, N, 3) en un solo pase vectorizado."""
    # frames de la cola: frame-(TRAIL-1) ... frame  (mod FRAMES)
    offs = np.arange(-(TRAIL - 1), 1, dtype=np.float64)
    ff = (frame + offs) % FRAMES
    # xi: (TRAIL, N)
    xi = xi0[None, :] + (2.0 * math.pi) * (ff[:, None] / FRAMES)
    z1_re, z1_im, z2_re, z2_im = hopf_s3(
        zeta[None, :], eta[None, :], xi
    )
    return stereo_project(z1_re, z1_im, z2_re, z2_im).astype(np.float32)


def seed_particles(rng):
    """
    Distribuye fibras en S² (Fibonacci-ish en (ζ, η)) y varias fases por fibra.
    Color fijo por fibra (hue = η, sat/val por ζ).
    """
    # Centros de fibra
    i = np.arange(N_FIBERS, dtype=np.float64)
    # Fibonacci-like covering of S² mapped to Hopf base angles
    golden = (math.sqrt(5.0) - 1.0) / 2.0
    # ζ ∈ (ZETA_MIN, ZETA_MAX) with denser sampling near equator for visual balance
    t = (i + 0.5) / N_FIBERS
    zeta_f = ZETA_MIN + (ZETA_MAX - ZETA_MIN) * t
    # Slight sin redistribution so poles aren't empty lines of infinity
    zeta_f = ZETA_MIN + (ZETA_MAX - ZETA_MIN) * (0.5 - 0.5 * np.cos(math.pi * t))
    eta_f = (2.0 * math.pi * i * golden) % (2.0 * math.pi)

    # Expand to N particles (repeat fibers + phase offsets)
    fiber_idx = np.arange(N) % N_FIBERS
    zeta = zeta_f[fiber_idx].astype(np.float64)
    eta = eta_f[fiber_idx].astype(np.float64)
    # Spread particles evenly along each fiber
    within = (np.arange(N) // N_FIBERS).astype(np.float64)
    max_per = max(1, (N + N_FIBERS - 1) // N_FIBERS)
    xi0 = (2.0 * math.pi * within / max_per).astype(np.float64)
    # Small jitter so trails don't alias into perfect grid lines
    xi0 = (xi0 + rng.uniform(-0.02, 0.02, size=N)) % (2.0 * math.pi)

    # Colores: arcoíris por η (fase base), brillo por ζ
    hue = (eta / (2.0 * math.pi)) % 1.0
    # sat/val: más brillantes cerca del ecuador de la base
    eq = np.sin(zeta)  # 0 at poles, 1 at equator
    sat = 0.75 + 0.25 * eq
    val = 0.55 + 0.45 * eq

    colors = hsv_to_rgb(hue, sat, val).astype(np.float32)
    return zeta, eta, xi0, colors, fiber_idx


def hsv_to_rgb(h, s, v):
    """Vectorized HSV→RGB, h,s,v in [0,1]."""
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


# --------------------------------------------------------------------------
# 2. Eventos de audio (periódicos / geométricos)
# --------------------------------------------------------------------------
def build_events(rng, zeta, eta, xi0):
    """Eventos suaves alineados al flujo de las fibras (sin caos)."""
    events = []
    # Un “burst” cada ~45 frames con nota según η media de un subset
    step = 45
    for f in range(step, FRAMES, step):
        # Intensidad suave sinusoidal (perfecto para loop)
        phase = 2.0 * math.pi * f / FRAMES
        intensity = 0.55 + 0.35 * abs(math.sin(phase * 2.0))
        note = str(rng.choice(["C3", "E3", "G3", "B3", "D4", "A3"]))
        events.append({
            "frame": f,
            "t_seconds": round(f / FPS, 4),
            "type": "fiber_pulse",
            "intensity": float(intensity),
            "note": note,
        })
    return events


# --------------------------------------------------------------------------
# 3. Cámara + render
# --------------------------------------------------------------------------
def cam_matrix(f):
    progress = f / max(1, FRAMES)
    # Órbita 360° exacta
    theta = math.radians(25) + math.radians(360) * progress
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    Rz = np.array([
        [cos_t, -sin_t, 0],
        [sin_t, cos_t, 0],
        [0, 0, 1],
    ])
    # Inclinación que vuelve al inicio
    phi = math.radians(32) + math.radians(12) * math.sin(progress * 2 * math.pi)
    cos_p, sin_p = np.cos(phi), np.sin(phi)
    Rx = np.array([
        [1, 0, 0],
        [0, cos_p, -sin_p],
        [0, sin_p, cos_p],
    ])
    return Rz @ Rx


def render_history(history, R, PROJ_SCALE, colors):
    """history: (TRAIL, N, 3)"""
    img = np.zeros((RES_H, RES_W, 3), dtype=np.float32)
    history_rot = history @ R.T

    X_screen = (history_rot[:, :, 0] * PROJ_SCALE + RES_W / 2).astype(int)
    Y_screen = (-history_rot[:, :, 2] * PROJ_SCALE + RES_H / 2).astype(int)

    for t in range(TRAIL):
        alpha = (t + 1) / TRAIL
        alpha *= 0.045

        xs = X_screen[t]
        ys = Y_screen[t]

        valid = (xs >= 0) & (xs < RES_W) & (ys >= 0) & (ys < RES_H)
        xs_v = xs[valid]
        ys_v = ys[valid]
        c_v = colors[valid]

        np.add.at(img[:, :, 0], (ys_v, xs_v), c_v[:, 0] * alpha)
        np.add.at(img[:, :, 1], (ys_v, xs_v), c_v[:, 1] * alpha)
        np.add.at(img[:, :, 2], (ys_v, xs_v), c_v[:, 2] * alpha)

    return img


def run():
    rng = np.random.default_rng(42)
    print(f"[hopf_numpy] Sembrando {N} partículas en {N_FIBERS} fibras Hopf...")
    zeta, eta, xi0, colors, _fiber_idx = seed_particles(rng)

    events = build_events(rng, zeta, eta, xi0)
    with open(EVENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "fps": FPS,
            "frames": FRAMES,
            "duration_s": round(FRAMES / FPS, 4),
            "resolution": [RES_W, RES_H],
            "engine": ENGINE,
            "system": "hopf_fibration",
            "events": events,
        }, fh, indent=2, ensure_ascii=False)
    print(f"[hopf_numpy] Eventos: {len(events)} -> {EVENTS_PATH}")

    # Escala visual: las fibras estereográficas viven ~ en bola de radio ~2–4
    PROJ_SCALE = 220.0 if FORMAT == "16:9" else 260.0

    print(f"[hopf_numpy] Renderizando {FRAMES} frames SEAMLESS (periódico exacto)...")

    for f in range(FRAMES):
        out_path = os.path.join(FRAMES_DIR, f"{f:04d}.png")
        if os.path.exists(out_path):
            continue

        R = cam_matrix(f)

        # Cola modular vectorizada → loop perfecto de trails
        hist = positions_trail(zeta, eta, xi0, f)
        img = render_history(hist, R, PROJ_SCALE, colors)

        # Bloom suave, look “fibras luminosas”
        bloom = scipy.ndimage.gaussian_filter(img, sigma=4.5)
        img = img + bloom * 1.0
        img = np.clip(img, 0, 1)

        Image.fromarray((img * 255).astype(np.uint8)).save(out_path)

        if f % 24 == 0 or f == FRAMES - 1:
            print(f"[hopf_numpy] frame {f + 1}/{FRAMES}")

    print("\n[hopf_numpy] ====== RESUMEN ======")
    print(f"[hopf_numpy] motor   : {ENGINE} ({RES_W}x{RES_H})")
    print(f"[hopf_numpy] frames  : {FRAMES} -> {FRAMES_DIR}")


if __name__ == "__main__":
    run()
