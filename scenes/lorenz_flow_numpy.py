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
FRAMES = int(arg("--frames", 360))
RES_H = int(arg("--res", 1024))
FORMAT = str(arg("--format", "9:16"))
if FORMAT == "9:16":
    RES_W = int(RES_H * 9 / 16)
else:
    RES_W = int(RES_H * 16 / 9)
SAMPLES = int(arg("--samples", 32)) # Ignored for Numpy
FPS = 60
NAME = str(arg("--name", "lorenz_native"))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

# --------------------------------------------------------------------------
# 1. Parámetros de la simulación
# --------------------------------------------------------------------------
N = 15000            # Muy alto para una apariencia fractal y suave
TRAIL = 45           # Cola larga
SEED_RADIUS = 0.1
SPEED = 0.5
DT = SPEED / FPS

# Lorenz Clásico
SIGMA = 10.0
RHO = 28.0
BETA = 8.0 / 3.0

def velocity(P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    dx = SIGMA * (y - x)
    dy = x * (RHO - z) - y
    dz = x * y - BETA * z
    return np.stack([dx, dy, dz], axis=1)

def rk4(P):
    k1 = velocity(P)
    k2 = velocity(P + 0.5 * DT * k1)
    k3 = velocity(P + 0.5 * DT * k2)
    k4 = velocity(P + DT * k3)
    return P + (DT / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

# --------------------------------------------------------------------------
# 2. Simulación
# --------------------------------------------------------------------------
def simulate():
    print(f"[lorenz_numpy] Simulando {N} partículas...")
    rng = np.random.default_rng(42)
    P = np.array([1.0, 1.0, 20.0]) + rng.normal(size=(N, 3)) * SEED_RADIUS
    
    # Warmup
    for _ in range(800):
        P = rk4(P)
        
    positions = np.zeros((FRAMES + TRAIL, N, 3), dtype=np.float32)
    events = []
    prev_com_x = None
    
    for f in range(FRAMES + TRAIL):
        positions[f] = P
        
        com = np.mean(P, axis=0)
        com_x = com[0]
        
        # Generar eventos musicales basados en el cruce de alas
        if f >= TRAIL:
            frame_render = f - TRAIL
            if prev_com_x is not None:
                if prev_com_x < 0 and com_x >= 0:
                    events.append({
                        "frame": frame_render,
                        "t_seconds": round(frame_render / FPS, 4),
                        "type": "wing_cross",
                        "wing": "right",
                        "note": "G3",
                        "intensity": 0.8
                    })
                elif prev_com_x > 0 and com_x <= 0:
                    events.append({
                        "frame": frame_render,
                        "t_seconds": round(frame_render / FPS, 4),
                        "type": "wing_cross",
                        "wing": "left",
                        "note": "C3",
                        "intensity": 0.8
                    })
            prev_com_x = com_x
        
        P = rk4(P)
        
    return positions, events

# --------------------------------------------------------------------------
# 3. Render
# --------------------------------------------------------------------------
def cam_matrix(f):
    progress = f / max(1, FRAMES - 1)
    # Orbita cámara 360 grados
    theta = math.radians(-120) + math.radians(360) * progress
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    Rz = np.array([
        [cos_t, -sin_t, 0],
        [sin_t, cos_t, 0],
        [0, 0, 1]
    ])
    
    # Inclinación lenta
    phi = math.radians(10) + math.radians(20) * math.sin(progress * math.pi)
    cos_p, sin_p = np.cos(phi), np.sin(phi)
    Rx = np.array([
        [1, 0, 0],
        [0, cos_p, -sin_p],
        [0, sin_p, cos_p]
    ])
    
    return Rz @ Rx

def run():
    positions, events = simulate()
    
    with open(EVENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "fps": FPS, "frames": FRAMES, "duration_s": round(FRAMES / FPS, 4),
            "resolution": [RES_W, RES_H], "engine": ENGINE, "events": events,
        }, fh, indent=2, ensure_ascii=False)
    print(f"[lorenz_numpy] Eventos generados: {len(events)} -> {EVENTS_PATH}")

    # Escalar base de la proyección
    PROJ_SCALE = 22.0 if FORMAT == "9:16" else 15.0
    
    colors = np.zeros((N, 3), dtype=np.float32)
    # Ala izquierda Magenta-Rosa, Ala derecha Cyan-Azul brillante
    left_mask = positions[0, :, 0] < 0
    colors[left_mask] = [1.0, 0.1, 0.6]  # Hot Magenta
    colors[~left_mask] = [0.0, 0.8, 1.0] # Cyan

    print(f"[lorenz_numpy] Renderizando {FRAMES} frames...")
    
    for f in range(FRAMES):
        out_path = os.path.join(FRAMES_DIR, f"{f:04d}.png")
        if os.path.exists(out_path):
            continue # Permitir reanudar si falla
            
        img = np.zeros((RES_H, RES_W, 3), dtype=np.float32)
        R = cam_matrix(f)
        
        # Historial (TRAIL) actual
        history = positions[f : f + TRAIL].copy()
        history[:, :, 2] -= 25.0 # Centrar atractor de Lorenz
        
        history_rot = history @ R.T
        
        X_screen = (history_rot[:, :, 0] * PROJ_SCALE + RES_W / 2).astype(int)
        Y_screen = (-history_rot[:, :, 2] * PROJ_SCALE + RES_H / 2).astype(int)
        
        for t in range(TRAIL):
            # Alpha de la cola (más transparente al principio de 'history', es decir, más antiguo)
            alpha = (t + 1) / TRAIL
            alpha *= 0.08 # Multiplicador maestro de intensidad
            
            xs = X_screen[t]
            ys = Y_screen[t]
            
            valid = (xs >= 0) & (xs < RES_W) & (ys >= 0) & (ys < RES_H)
            xs_v = xs[valid]
            ys_v = ys[valid]
            c_v = colors[valid]
            
            np.add.at(img[:, :, 0], (ys_v, xs_v), c_v[:, 0] * alpha)
            np.add.at(img[:, :, 1], (ys_v, xs_v), c_v[:, 1] * alpha)
            np.add.at(img[:, :, 2], (ys_v, xs_v), c_v[:, 2] * alpha)
            
        # Post-procesamiento Bloom (Efecto brillo de neón)
        bloom = scipy.ndimage.gaussian_filter(img, sigma=3.0)
        img = img + bloom * 0.75
        
        # Tone mapping
        img = np.clip(img, 0, 1)
        
        Image.fromarray((img * 255).astype(np.uint8)).save(out_path)
        
        if f % 24 == 0 or f == FRAMES - 1:
            print(f"[lorenz_numpy] frame {f + 1}/{FRAMES}")
            
    print("\n[lorenz_numpy] ====== RESUMEN ======")
    print(f"[lorenz_numpy] motor   : {ENGINE} ({RES_W}x{RES_H})")
    print(f"[lorenz_numpy] frames  : {FRAMES} -> {FRAMES_DIR}")

if __name__ == "__main__":
    run()
