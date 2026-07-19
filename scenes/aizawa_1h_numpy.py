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
NAME = str(arg("--name", "aizawa_1h_native"))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

# --------------------------------------------------------------------------
# 1. Parámetros de la simulación
# --------------------------------------------------------------------------
N = 30000            # Ultra alta densidad
TRAIL = 40           # Cola
SPEED = 0.05         # Aizawa suele ser muy rápido, bajamos velocidad
DT = SPEED / FPS

# Parámetros del Aizawa Attractor
A = 0.95
B = 0.7
C = 0.6
D = 3.5
E = 0.25
F = 0.1

def velocity(P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    dx = (z - B) * x - D * y
    dy = D * x + (z - B) * y
    dz = C + A * z - (z**3) / 3.0 - (x**2 + y**2) * (1.0 + E * z) + F * z * (x**3)
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
    print(f"[aizawa_numpy] Simulando {N} partículas para bucle seamless...")
    rng = np.random.default_rng(42)
    
    # Inicialización cerca del origen
    P = rng.uniform(-0.1, 0.1, size=(N, 3)).astype(np.float32)
    P[:, 2] += 1.0 # Offset en z para evitar el punto de equilibrio inestable
    
    # Warmup para que se adhieran perfectamente al atractor
    print("[aizawa_numpy] Calentamiento (Warmup)...")
    for _ in range(2500):
        P = rk4(P)
        
    total_frames = 2 * FRAMES + TRAIL
    positions = np.zeros((total_frames, N, 3), dtype=np.float32)
    events = []
    
    prev_mean_speed = 0.0
    
    for f in range(total_frames):
        positions[f] = P
        
        # Audio events logic
        if f < FRAMES:
            vel = velocity(P)
            spd = np.sqrt(np.sum(vel**2, axis=1))
            mean_speed = float(np.mean(spd))
            if f > 10 and mean_speed > prev_mean_speed * 1.5 and mean_speed > 0.5:
                note = str(rng.choice(["C3", "E3", "G3", "B3", "D4"]))
                events.append({
                    "frame": f,
                    "t_seconds": round(f / FPS, 4),
                    "type": "chaos_burst",
                    "intensity": float(min(1.5, mean_speed * 0.8)),
                    "note": note
                })
            prev_mean_speed = mean_speed
        
        P = rk4(P)
        
    return positions, events

# --------------------------------------------------------------------------
# 3. Render
# --------------------------------------------------------------------------
def cam_matrix(f):
    progress = f / max(1, FRAMES)
    # Orbita 360 grados exactos
    theta = math.radians(0) + math.radians(360) * progress
    cos_t, sin_t = np.cos(theta), np.sin(theta)
    Rz = np.array([
        [cos_t, -sin_t, 0],
        [sin_t, cos_t, 0],
        [0, 0, 1]
    ])
    
    # Inclinación que vuelve a su punto inicial
    phi = math.radians(45) + math.radians(15) * math.sin(progress * 2 * math.pi)
    cos_p, sin_p = np.cos(phi), np.sin(phi)
    Rx = np.array([
        [1, 0, 0],
        [0, cos_p, -sin_p],
        [0, sin_p, cos_p]
    ])
    
    return Rz @ Rx

def render_history(history, R, PROJ_SCALE, colors):
    img = np.zeros((RES_H, RES_W, 3), dtype=np.float32)
    
    # Offset central porque el atractor de Aizawa está típicamente centrado alrededor de z=0.7
    offset = np.array([0, 0, 0.7], dtype=np.float32)
    
    # Rota y proyecta
    history_rot = (history - offset) @ R.T
    
    X_screen = (history_rot[:, :, 0] * PROJ_SCALE + RES_W / 2).astype(int)
    Y_screen = (-history_rot[:, :, 2] * PROJ_SCALE + RES_H / 2).astype(int)
    
    for t in range(TRAIL):
        alpha = (t + 1) / TRAIL
        alpha *= 0.04 # Sensibilidad general para 30000 partículas
        
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
    positions, events = simulate()
    
    with open(EVENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "fps": FPS, "frames": FRAMES, "duration_s": round(FRAMES / FPS, 4),
            "resolution": [RES_W, RES_H], "engine": ENGINE, "events": events,
        }, fh, indent=2, ensure_ascii=False)

    # El atractor de Aizawa es muy denso, tamaño típico de la malla es de ~2.0
    PROJ_SCALE = 380.0 if FORMAT == "16:9" else 420.0
    
    colors = np.zeros((N, 3), dtype=np.float32)
    # Asignar color por distancia vertical z
    z_vals = positions[0, :, 2]
    # Rango de z suele ser de -1 a 2
    z_norm = np.clip((z_vals + 1.0) / 3.0, 0, 1)
    
    # Gradiente: Cósmico (Púrpura Profundo -> Cian brillante -> Dorado)
    for i in range(N):
        v = z_norm[i]
        if v < 0.5:
            f = v * 2.0
            # Púrpura a Cian
            colors[i] = [0.2 - 0.2*f, 0.0 + 0.8*f, 0.8 + 0.2*f]
        else:
            f = (v - 0.5) * 2.0
            # Cian a Dorado
            colors[i] = [0.0 + 1.0*f, 0.8, 1.0 - 0.8*f]

    print(f"[aizawa_numpy] Renderizando {FRAMES} frames SEAMLESS...")
    
    for f in range(FRAMES):
        out_path = os.path.join(FRAMES_DIR, f"{f:04d}.png")
        if os.path.exists(out_path):
            continue 
            
        R = cam_matrix(f)
        
        # Seamless time blending algorithm
        alpha = f / FRAMES
        
        h1 = positions[f : f + TRAIL].copy()
        h2 = positions[f + FRAMES : f + FRAMES + TRAIL].copy()
        
        img1 = render_history(h1, R, PROJ_SCALE, colors)
        img2 = render_history(h2, R, PROJ_SCALE, colors)
        
        # Mezcla perfecta
        img = img1 * (1.0 - alpha) + img2 * alpha
            
        # Post-procesamiento Bloom intenso para Aizawa (Cosmic Sphere)
        bloom = scipy.ndimage.gaussian_filter(img, sigma=5.0)
        img = img + bloom * 1.2
        
        img = np.clip(img, 0, 1)
        
        Image.fromarray((img * 255).astype(np.uint8)).save(out_path)
        
        if f % 24 == 0 or f == FRAMES - 1:
            print(f"[aizawa_numpy] frame {f + 1}/{FRAMES}")
            
    print("\n[aizawa_numpy] ====== RESUMEN ======")
    print(f"[aizawa_numpy] motor   : {ENGINE} ({RES_W}x{RES_H})")
    print(f"[aizawa_numpy] frames  : {FRAMES} -> {FRAMES_DIR}")

if __name__ == "__main__":
    run()
