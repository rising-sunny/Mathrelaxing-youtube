import numpy as np
from PIL import Image
import os
import scipy.ndimage

# 1. Parámetros
W, H = 576, 1024
N = 10000
TRAIL = 40
FRAMES = 1

# Lorenz
SIGMA, RHO, BETA = 10.0, 28.0, 8.0/3.0
DT = 0.4 / 60

# 2. Funciones
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

# 3. Simulación rápida
print("Simulando...")
rng = np.random.default_rng(42)
P = np.array([1.0, 1.0, 20.0]) + rng.normal(size=(N, 3)) * 0.1

for _ in range(500):
    P = rk4(P)

history = []
for _ in range(TRAIL):
    history.append(P)
    P = rk4(P)

history = np.array(history)

# 4. Proyección 2D
history[:, :, 2] -= 25.0

theta = np.radians(45)
cos_t, sin_t = np.cos(theta), np.sin(theta)
Rz = np.array([
    [cos_t, -sin_t, 0],
    [sin_t, cos_t, 0],
    [0, 0, 1]
])

phi = np.radians(15)
cos_p, sin_p = np.cos(phi), np.sin(phi)
Rx = np.array([
    [1, 0, 0],
    [0, cos_p, -sin_p],
    [0, sin_p, cos_p]
])

R = Rz @ Rx
history_rot = history @ R.T

SCALE = 22.0
X_screen = (history_rot[:, :, 0] * SCALE + W / 2).astype(int)
# Invertimos Y para gráficos (0 es arriba en PIL)
Y_screen = (-history_rot[:, :, 2] * SCALE + H / 2).astype(int)

# 5. Renderizado en grilla de numpy
print("Renderizando...")
img = np.zeros((H, W, 3), dtype=np.float32)

colors = np.zeros((N, 3), dtype=np.float32)
left_mask = history[-1, :, 0] < 0
colors[left_mask] = [0.1, 0.5, 1.0]
colors[~left_mask] = [1.0, 0.4, 0.1]

for t in range(TRAIL):
    alpha = (t + 1) / TRAIL
    alpha *= 0.1 # Opacidad ajustada para 10000 particulas
    
    xs = X_screen[t]
    ys = Y_screen[t]
    
    valid = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
    xs = xs[valid]
    ys = ys[valid]
    c = colors[valid]
    
    np.add.at(img[:, :, 0], (ys, xs), c[:, 0] * alpha)
    np.add.at(img[:, :, 1], (ys, xs), c[:, 1] * alpha)
    np.add.at(img[:, :, 2], (ys, xs), c[:, 2] * alpha)

# Aplicar pequeño Glow (Bloom) con Scipy
print("Aplicando Glow...")
bloom = scipy.ndimage.gaussian_filter(img, sigma=2.0)
img = img + bloom * 0.5

# Tone mapping ACES-like o simple clip
img = np.clip(img, 0, 1)

out_path = os.path.join(os.path.dirname(__file__), "test_render.png")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
Image.fromarray((img * 255).astype(np.uint8)).save(out_path)
print(f"Guardado en {out_path}")
