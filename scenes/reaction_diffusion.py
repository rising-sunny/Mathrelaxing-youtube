"""
Reaction-Diffusion (Gray-Scott) — Direct frame renderer
Generates 576x1024 vertical frames using numpy + PIL.
No Blender needed. Beautiful neon colormap on dark background.
"""
import numpy as np
from PIL import Image, ImageFilter
import os
import sys
import json

def make_colormap():
    """Custom neon colormap: black -> deep blue -> cyan -> green -> white"""
    N = 256
    cmap = np.zeros((N, 3), dtype=np.uint8)
    for i in range(N):
        t = i / (N - 1)
        if t < 0.15:
            # Black to deep blue
            s = t / 0.15
            r, g, b = 0, 0, int(40 * s)
        elif t < 0.35:
            # Deep blue to electric blue
            s = (t - 0.15) / 0.20
            r = int(5 * s)
            g = int(30 + 80 * s)
            b = int(40 + 170 * s)
        elif t < 0.55:
            # Electric blue to cyan
            s = (t - 0.35) / 0.20
            r = int(5 + 15 * s)
            g = int(110 + 130 * s)
            b = int(210 + 45 * s)
        elif t < 0.75:
            # Cyan to green-white
            s = (t - 0.55) / 0.20
            r = int(20 + 100 * s)
            g = int(240 + 15 * s)
            b = int(255 - 60 * s)
        else:
            # Green-white to white
            s = (t - 0.75) / 0.25
            r = int(120 + 135 * s)
            g = 255
            b = int(195 + 60 * s)
        cmap[i] = [min(r, 255), min(g, 255), min(b, 255)]
    return cmap

def apply_glow(img, radius=3, intensity=0.4):
    """Add a subtle glow effect by blending with a blurred version"""
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    return Image.blend(img, blurred, intensity)

def run_simulation(grid_w=256, frames=900, fps=60,
                   out_w=576, out_h=1024, outdir=None, seed=42):
    # Use rectangular grid matching 9:16 aspect ratio
    grid_h = int(grid_w * 16 / 9)  # e.g. 256 -> 455
    
    if outdir is None:
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        outdir = os.path.join(repo, "output", "shorts_reaction", "frames")
    os.makedirs(outdir, exist_ok=True)
    
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    events_path = os.path.join(repo, "data", "shorts_reaction_events.json")
    os.makedirs(os.path.dirname(events_path), exist_ok=True)

    cmap = make_colormap()

    # --- Initialize Gray-Scott on rectangular grid ---
    A = np.ones((grid_h, grid_w), dtype=np.float64)
    B = np.zeros((grid_h, grid_w), dtype=np.float64)

    # Scatter seeds across the entire grid.
    # La semilla es parametrizable: la simulacion es determinista, asi que
    # cambiarla es lo que produce un patron nuevo en vez de repetir el video ya
    # publicado.
    np.random.seed(seed)
    n_seeds = 25
    for _ in range(n_seeds):
        cx = np.random.randint(10, grid_h - 10)
        cy = np.random.randint(10, grid_w - 10)
        r = np.random.randint(3, 8)
        B[cx - r:cx + r, cy - r:cy + r] = 1.0
        A[cx - r:cx + r, cy - r:cy + r] = 0.5

    # Add small noise to break symmetry
    B += 0.05 * np.random.uniform(0, 1, (grid_h, grid_w)) * (B > 0)

    # Diffusion rates
    DA = 1.0
    DB = 0.5
    dt = 1.0
    substeps = 12

    # Feed/kill schedule — all stable regimes that stay visually rich
    stages = [
        {"f": 0.0367, "k": 0.0649, "dur": 0.25},  # Mitosis (dividing spots)
        {"f": 0.0545, "k": 0.0620, "dur": 0.25},  # Coral / worms
        {"f": 0.0290, "k": 0.0570, "dur": 0.25},  # Maze / labyrinth
        {"f": 0.0367, "k": 0.0649, "dur": 0.25},  # Back to spots
    ]

    events = []
    
    def laplacian(X):
        """9-point stencil Laplacian with wrapping"""
        return (
            0.20 * (np.roll(X, 1, 0) + np.roll(X, -1, 0) +
                    np.roll(X, 1, 1) + np.roll(X, -1, 1)) +
            0.05 * (np.roll(np.roll(X, 1, 0), 1, 1) +
                    np.roll(np.roll(X, -1, 0), 1, 1) +
                    np.roll(np.roll(X, 1, 0), -1, 1) +
                    np.roll(np.roll(X, -1, 0), -1, 1)) -
            1.0 * X
        )

    # Pre-warm the simulation for 300 steps so we start with visible patterns
    feed0, kill0 = stages[0]["f"], stages[0]["k"]
    print(f"Pre-warming simulation on {grid_h}x{grid_w} grid...")
    for _ in range(300):
        for _ in range(substeps):
            lapA = laplacian(A)
            lapB = laplacian(B)
            abb = A * B * B
            A += (DA * lapA - abb + feed0 * (1.0 - A)) * dt
            B += (DB * lapB + abb - (kill0 + feed0) * B) * dt
            A = np.clip(A, 0, 1)
            B = np.clip(B, 0, 1)
    
    print(f"Pre-warm done. B range: [{B.min():.4f}, {B.max():.4f}]")

    for f in range(frames):
        # Determine current feed/kill from schedule
        t_norm = f / frames
        cum = 0
        feed, kill = stages[0]["f"], stages[0]["k"]
        for si, st in enumerate(stages):
            if t_norm < cum + st["dur"]:
                # Interpolate within stage
                local_t = (t_norm - cum) / st["dur"]
                if si + 1 < len(stages):
                    nxt = stages[si + 1]
                    blend = max(0, (local_t - 0.7) / 0.3)  # blend in last 30%
                    feed = st["f"] * (1 - blend) + nxt["f"] * blend
                    kill = st["k"] * (1 - blend) + nxt["k"] * blend
                else:
                    feed, kill = st["f"], st["k"]
                break
            cum += st["dur"]

        # Record events
        B_total = float(B.sum()) / (grid_h * grid_w)
        events.append({
            "frame": f,
            "t": round(f / fps, 4),
            "feed": round(feed, 5),
            "kill": round(kill, 5),
            "B_total": round(B_total, 6)
        })

        # --- Simulation substeps ---
        for _ in range(substeps):
            lapA = laplacian(A)
            lapB = laplacian(B)
            abb = A * B * B
            A += (DA * lapA - abb + feed * (1.0 - A)) * dt
            B += (DB * lapB + abb - (kill + feed) * B) * dt
            A = np.clip(A, 0, 1)
            B = np.clip(B, 0, 1)

        # --- Render frame ---
        # Use fixed range [0, 0.45] for stable coloring across all frames
        b_norm = np.clip(B / 0.45, 0, 1)
        
        indices = (b_norm * 255).astype(np.uint8)
        rgb = cmap[indices]  # shape (grid_h, grid_w, 3)

        # Create PIL image and resize to exact output resolution
        img = Image.fromarray(rgb, mode='RGB')
        canvas = img.resize((out_w, out_h), Image.LANCZOS)
        
        # Add glow effect
        canvas = apply_glow(canvas, radius=4, intensity=0.35)

        # Save
        out_path = os.path.join(outdir, f"{f:04d}.png")
        canvas.save(out_path)

        if f % 50 == 0:
            print(f"Frame {f}/{frames}  f={feed:.5f}  k={kill:.5f}  "
                  f"B=[{B.min():.4f},{B.max():.4f}]")

    # Save events
    with open(events_path, "w", encoding="utf-8") as jf:
        json.dump({"duration_s": frames / fps, "fps": fps, "events": events}, jf)
    print(f"Done! {frames} frames saved to {outdir}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=900)
    parser.add_argument("--grid", type=int, default=256)
    parser.add_argument("--width", type=int, default=576)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=42,
                        help="Semilla del patron inicial. Cambiala para obtener "
                             "un patron distinto (la simulacion es determinista).")
    args = parser.parse_args()

    run_simulation(grid_w=args.grid, frames=args.frames,
                   out_w=args.width, out_h=args.height, seed=args.seed)
