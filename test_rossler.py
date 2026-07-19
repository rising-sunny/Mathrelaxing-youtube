import numpy as np

def velocity_rossler(P):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    dx = -y - z
    dy = x + 0.2 * y
    dz = 0.2 + z * (x - 5.7)
    return np.stack([dx, dy, dz], axis=1)

def rk4(P, dt):
    k1 = velocity_rossler(P)
    k2 = velocity_rossler(P + 0.5 * dt * k1)
    k3 = velocity_rossler(P + 0.5 * dt * k2)
    k4 = velocity_rossler(P + dt * k3)
    return P + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

P0 = np.array([[10.0, 0.0, 0.0]])
rng = np.random.default_rng(42)
P = P0 + rng.normal(size=(1000, 3)) * 0.01
dt = 0.6 / 24
print(f"Initial: {np.mean(P, axis=0)}")
for f in range(360):
    P = rk4(P, dt)
    if np.isnan(P).any() or np.isinf(P).any() or np.max(np.abs(P)) > 1000:
        print(f"Exploded at frame {f}! Max val: {np.max(np.abs(P))}")
        break
    if f % 50 == 0:
        print(f"Frame {f}: {P}")
