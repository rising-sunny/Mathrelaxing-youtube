import sys
import os
import json
import math
import numpy as np
import scipy.special
import scipy.ndimage
from PIL import Image

# --------------------------------------------------------------------------
# 0. Argumentos
# --------------------------------------------------------------------------
argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]

def arg(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default

ENGINE = str(arg("--engine", "numpy")).lower()
FRAMES = int(arg("--frames", 900))
RES_H = int(arg("--res", 1024))
FORMAT = str(arg("--format", "9:16"))
if FORMAT == "9:16":
    RES_W = int(RES_H * 9 / 16)
else:
    RES_W = int(RES_H * 16 / 9)
FPS = 60
NAME = str(arg("--name", "circular_cymatics"))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

# --------------------------------------------------------------------------
# 1. Parámetros de la simulación
# --------------------------------------------------------------------------
N = 300000           # 300,000 granos de arena!
SPEED = 0.08         # Velocidad de caída hacia los nodos
NOISE = 0.005        # Agitación aleatoria (para evitar atascos locales)
RADIUS = 1.0         # Radio de la placa circular

# Definición de los modos (n = diámetros nodales, k = escala radial relacionada con círculos nodales)
# Frecuencias inventadas pero armónicamente agradables para el audio
MODES = [
    {"n": 0, "k": 12.0, "freq": 220},   # Círculos
    {"n": 3, "k": 16.0, "freq": 330},   # Hexágono estrellado
    {"n": 5, "k": 19.0, "freq": 440},   # Estrella de 10 puntas
    {"n": 2, "k": 25.0, "freq": 550},   # Cruz super densa
    {"n": 7, "k": 22.0, "freq": 660}    # Mandala denso
]

def bessel_mode(P, n, k):
    r = np.hypot(P[:,0], P[:,1])
    theta = np.arctan2(P[:,1], P[:,0])
    # Amplitud absoluta
    val = np.abs(scipy.special.jv(n, k * r) * np.cos(n * theta))
    # Máscara para la placa circular
    val[r > RADIUS] = 10.0 # Borde es antinodo gigante para rechazar la arena
    return val

# Grids precalculados para aceleración extrema
GRID_RES = 1000
GRID_EXTENT = 1.2
x_lin = np.linspace(-GRID_EXTENT, GRID_EXTENT, GRID_RES)
y_lin = np.linspace(-GRID_EXTENT, GRID_EXTENT, GRID_RES)
X_grid, Y_grid = np.meshgrid(x_lin, y_lin)
P_grid = np.stack([X_grid.flatten(), Y_grid.flatten()], axis=1)

def eval_field_grid(t_norm):
    num_transitions = len(MODES) - 1
    t_scaled = t_norm * num_transitions
    idx = int(t_scaled)
    alpha = t_scaled - idx
    
    alpha = alpha * alpha * (3 - 2 * alpha)
    
    if idx >= num_transitions:
        v = bessel_mode(P_grid, MODES[-1]["n"], MODES[-1]["k"])
    else:
        m1 = MODES[idx]
        m2 = MODES[idx+1]
        v1 = bessel_mode(P_grid, m1["n"], m1["k"])
        v2 = bessel_mode(P_grid, m2["n"], m2["k"])
        v = v1 * (1 - alpha) + v2 * alpha
        
    return v.reshape(GRID_RES, GRID_RES)

# --------------------------------------------------------------------------
# 2. Simulación y Render Interleaved
# --------------------------------------------------------------------------
def run():
    print(f"[cymatics] Inicializando {N} partículas...")
    rng = np.random.default_rng(42)
    
    r_init = np.sqrt(rng.uniform(0, 1, N)) * RADIUS
    theta_init = rng.uniform(0, 2*np.pi, N)
    P = np.stack([r_init * np.cos(theta_init), r_init * np.sin(theta_init)], axis=1).astype(np.float32)
    
    PROJ_SCALE = min(RES_W, RES_H) / 2.2
    events = []
    prev_idx = -1
    
    for f in range(FRAMES):
        out_path = os.path.join(FRAMES_DIR, f"{f:04d}.png")
        t_norm = f / max(1, FRAMES - 1)
        
        # Precomputar el campo y gradiente para este fotograma en la grilla
        F_map = eval_field_grid(t_norm)
        # Gradientes usando sobel o diff central
        dF_dy, dF_dx = np.gradient(F_map)
        dF_dx = dF_dx / (2 * GRID_EXTENT / GRID_RES)
        dF_dy = dF_dy / (2 * GRID_EXTENT / GRID_RES)
        
        # Función para muestrear la grilla rápidamente
        def sample_grid(pts, grid):
            # Normalizar coordenadas de [-GRID_EXTENT, GRID_EXTENT] a [0, GRID_RES-1]
            ix = ((pts[:, 0] + GRID_EXTENT) / (2 * GRID_EXTENT) * (GRID_RES - 1)).astype(int)
            iy = ((pts[:, 1] + GRID_EXTENT) / (2 * GRID_EXTENT) * (GRID_RES - 1)).astype(int)
            ix = np.clip(ix, 0, GRID_RES - 1)
            iy = np.clip(iy, 0, GRID_RES - 1)
            return grid[iy, ix]

        num_transitions = len(MODES) - 1
        t_scaled = t_norm * num_transitions
        idx = int(t_scaled)
        if idx != prev_idx and idx < len(MODES):
            events.append({
                "frame": f,
                "t_seconds": round(f / FPS, 4),
                "type": "mode_change",
                "freq": MODES[idx]["freq"],
                "n": MODES[idx]["n"]
            })
            prev_idx = idx
            
        if not os.path.exists(out_path):
            # --- RENDER ---
            img = np.zeros((RES_H, RES_W, 3), dtype=np.float32)
            
            xs = (P[:,0] * PROJ_SCALE + RES_W / 2).astype(int)
            ys = (-P[:,1] * PROJ_SCALE + RES_H / 2).astype(int)
            
            valid = (xs >= 0) & (xs < RES_W) & (ys >= 0) & (ys < RES_H)
            
            # Colores: del amarillo (lento) al rojo carmesí (rápido)
            mag = sample_grid(P, F_map) # usamos amplitud del campo para color
            
            # mag es típicamente 0 a 0.5
            color_factor = np.clip(mag * 3.0, 0, 1)
            
            R_c = np.ones_like(color_factor)
            G_c = 0.8 * (1 - color_factor)
            B_c = 0.1 * (1 - color_factor)
            
            np.add.at(img[:, :, 0], (ys[valid], xs[valid]), R_c[valid] * 0.15)
            np.add.at(img[:, :, 1], (ys[valid], xs[valid]), G_c[valid] * 0.15)
            np.add.at(img[:, :, 2], (ys[valid], xs[valid]), B_c[valid] * 0.15)
            
            # Bloom (brillo etéreo)
            bloom = scipy.ndimage.gaussian_filter(img, sigma=2.0)
            img = img + bloom * 0.6
            
            img = np.clip(img, 0, 1)
            Image.fromarray((img * 255).astype(np.uint8)).save(out_path)
            
        if f % 30 == 0:
            print(f"[cymatics] fotograma {f}/{FRAMES}")
            
        # --- PHYSICS STEP ---
        # 3 sub-steps para mayor suavidad
        for _ in range(3):
            # Muestrear el gradiente desde la grilla
            gx = sample_grid(P, dF_dx)
            gy = sample_grid(P, dF_dy)
            
            # Normalizar
            mag_g = np.hypot(gx, gy)
            gx = gx / (mag_g + 0.1)
            gy = gy / (mag_g + 0.1)
            
            # Las partículas caen hacia donde la amplitud es menor
            P[:,0] -= gx * SPEED * (1.0/3.0)
            P[:,1] -= gy * SPEED * (1.0/3.0)
            
            # Agitación aleatoria
            mag_field = sample_grid(P, F_map)
            noise_amp = NOISE * (mag_field + 0.1)
            P[:,0] += rng.normal(0, 1, N) * noise_amp
            P[:,1] += rng.normal(0, 1, N) * noise_amp
            
            # Límite duro (borde del plato circular)
            r = np.hypot(P[:,0], P[:,1])
            out = r > RADIUS
            P[out, 0] = P[out, 0] * (RADIUS / r[out])
            P[out, 1] = P[out, 1] * (RADIUS / r[out])

    # Guardar eventos
    with open(EVENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "fps": FPS, "frames": FRAMES, "duration_s": round(FRAMES / FPS, 4),
            "resolution": [RES_W, RES_H], "engine": ENGINE, "events": events,
        }, fh, indent=2, ensure_ascii=False)
    print(f"[cymatics] Eventos guardados en {EVENTS_PATH}")

if __name__ == "__main__":
    run()
