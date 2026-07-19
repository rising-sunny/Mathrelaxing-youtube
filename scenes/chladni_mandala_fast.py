"""
chladni_mandala_fast.py — Placa de Chladni circular (mandala a color), SIN Blender.

Simula la misma fisica que chladni_mandala.py (bpy) pero rasteriza cada
fotograma directamente con numpy + Pillow (splat aditivo + blur = grano de
arena con brillo), lo que evita el costo de raytracing/rasterizado 3D de
Blender. Pensado para terminar en minutos en vez de horas.

    python scenes/chladni_mandala_fast.py --frames 900 --res 1024 --format 9:16 --name shorts_mandala
"""
import argparse
import json
import os

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter


def hsv_to_rgb_np(h, s, v):
    h = np.mod(h, 1.0) * 6.0
    i = np.floor(h).astype(np.int32) % 6
    f = h - np.floor(h)
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    r = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [v, q, p, p, t, v])
    g = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [t, v, v, q, p, p])
    b = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [p, p, t, v, v, q])
    return r, g, b


def make_plate_background(res_w, res_h):
    yy, xx = np.mgrid[0:res_h, 0:res_w].astype(np.float32)
    cx, cy = res_w / 2.0, res_h / 2.0
    scale = min(res_w, res_h) / 2.0 * 0.98
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / scale

    plate = np.zeros((res_h, res_w, 3), dtype=np.float32)
    inside = dist <= 1.0
    # placa metalica oscura con un leve resplandor especular arriba-izquierda
    spec = np.clip(1.0 - np.sqrt((xx - cx * 0.7) ** 2 + (yy - cy * 0.6) ** 2) / (scale * 1.8), 0, 1) ** 3
    base = 0.05 + 0.05 * spec
    for c in range(3):
        plate[..., c] = np.where(inside, base, 0.0)

    # aro del borde de la placa
    rim = (dist > 0.97) & (dist <= 1.0)
    plate[rim] = [0.02, 0.02, 0.025]

    # vinieta suave fuera de la placa (fondo del estudio)
    outside_glow = np.clip(1.0 - (dist - 1.0) * 2.0, 0, 1) * 0.03
    for c in range(3):
        plate[..., c] = np.maximum(plate[..., c], outside_glow * (0 if inside.any() else 0))

    vignette = np.clip(1.15 - dist * 0.35, 0.55, 1.0)
    return plate, vignette[..., None], inside


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=900)
    ap.add_argument("--res", type=int, default=1024)
    ap.add_argument("--format", type=str, default="9:16")
    ap.add_argument("--name", type=str, default="shorts_mandala")
    ap.add_argument("--particles", type=int, default=300000)
    args = ap.parse_args()

    res_h = args.res
    res_w = args.res if args.format == "1:1" else int(args.res * 9 / 16)

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(repo, "output", args.name)
    frames_dir = os.path.join(outdir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    N = args.particles
    fps = 60
    frames = args.frames
    substeps = 4
    dt = (1.0 / fps) / substeps

    rng = np.random.default_rng(42)
    ang0 = rng.uniform(0, 2 * np.pi, size=N)
    rad0 = np.sqrt(rng.uniform(0, 1.0, size=N)) * 0.9
    P = np.zeros((N, 3), dtype=np.float64)
    P[:, 0] = rad0 * np.cos(ang0)
    P[:, 1] = rad0 * np.sin(ang0)
    P[:, 2] = rng.uniform(0.0, 0.2, size=N)
    V = np.zeros((N, 3), dtype=np.float64)
    glow = np.zeros(N, dtype=np.float64)

    # Escalada dramatica: de un modo simple a un mandala de gran complejidad.
    # OJO: cuando m == n la formula de onda se anula (W=0 en todo el plato),
    # nunca debe ser la primera nota ni aparecer sin estructura previa.
    melody = [
        (1, 2), (2, 2), (1, 3), (2, 3), (1, 4),
        (2, 4), (3, 4), (3, 5), (4, 5), (4, 6),
        (5, 6), (5, 7), (6, 7), (6, 8), (7, 8),
    ]

    plate_bg, vignette, inside_mask = make_plate_background(res_w, res_h)
    scale_px = min(res_w, res_h) / 2.0 * 0.98
    cx, cy = res_w / 2.0, res_h / 2.0

    events_export = []
    hue_spin = 0.0

    for f in range(frames):
        note_idx = min(f // 60, len(melody) - 1)
        m, n = melody[note_idx]

        frame_in_note = f % 60
        speed = max(0.0, 1.0 - (frame_in_note / 10.0)) if frame_in_note < 10 else 0.0

        events_export.append({"frame": f, "m": m, "n": n, "speed": speed})
        hue_spin += 0.0006

        glow *= 0.92

        for _ in range(substeps):
            r = np.sqrt(P[:, 0] ** 2 + P[:, 1] ** 2)
            theta = np.arctan2(P[:, 1], P[:, 0])

            W = (np.cos(n * np.pi * r * 2.0) * np.cos(m * theta)
                 - np.cos(m * np.pi * r * 2.0) * np.cos(n * theta))

            on_plate = P[:, 2] <= 0.005
            V[:, 2] -= 9.81 * dt

            kick = np.abs(W) * 150.0 * dt
            kick = kick ** 1.5
            kick = kick * (1.0 + speed * 5.0)

            random_kick = kick * rng.uniform(0.5, 1.5, size=N)

            V[on_plate, 2] = np.abs(V[on_plate, 2]) * 0.6 + random_kick[on_plate]

            scatter = rng.normal(0, 1.0, size=(N, 2)) * random_kick[:, np.newaxis] * 0.8
            V[on_plate, :2] += scatter[on_plate]

            jitter = rng.normal(0, 1.0, size=(N, 2)) * 0.5 * dt
            V[on_plate, :2] += jitter[on_plate]

            dist = np.sqrt(P[:, 0] ** 2 + P[:, 1] ** 2)
            margin = 0.95
            over = np.maximum(dist - margin, 0.0)
            safe_dist = np.maximum(dist, 1e-6)
            dir_x = P[:, 0] / safe_dist
            dir_y = P[:, 1] / safe_dist
            V[:, 0] -= dir_x * over * 100.0 * dt
            V[:, 1] -= dir_y * over * 100.0 * dt

            V[on_plate, :2] *= 0.94
            V[:, :2] *= 0.99

            P += V * dt

            dist2 = np.sqrt(P[:, 0] ** 2 + P[:, 1] ** 2)
            over2 = dist2 > 0.98
            scale = np.where(over2, 0.98 / np.maximum(dist2, 1e-6), 1.0)
            P[:, 0] *= scale
            P[:, 1] *= scale
            P[:, 2] = np.maximum(P[:, 2], 0.0)

            glow[on_plate] = np.maximum(glow[on_plate], np.clip(random_kick[on_plate] / 0.35, 0.0, 1.0))

        # --- Color por grano ---
        r_final = np.sqrt(P[:, 0] ** 2 + P[:, 1] ** 2)
        theta_final = np.arctan2(P[:, 1], P[:, 0])
        hue = (theta_final / (2 * np.pi) + hue_spin) % 1.0
        sat = np.clip(0.55 + 0.25 * r_final, 0.0, 0.95)
        val = np.clip(0.4 + 0.6 * glow, 0.15, 1.0)
        rr, gg, bb = hsv_to_rgb_np(hue, sat, val)

        # --- Rasterizado directo (splat aditivo por densidad + color) ---
        px = np.clip((cx + P[:, 0] * scale_px).astype(np.int32), 0, res_w - 1)
        py = np.clip((cy - P[:, 1] * scale_px).astype(np.int32), 0, res_h - 1)
        idx = py * res_w + px

        flat_size = res_w * res_h
        acc_r = np.bincount(idx, weights=rr, minlength=flat_size)
        acc_g = np.bincount(idx, weights=gg, minlength=flat_size)
        acc_b = np.bincount(idx, weights=bb, minlength=flat_size)

        accum = np.stack([acc_r, acc_g, acc_b], axis=1).reshape(res_h, res_w, 3).astype(np.float32)
        accum *= 0.85  # normaliza densidad ~1 grano/pixel a brillo razonable

        glow_layer = gaussian_filter(accum, sigma=(3.5, 3.5, 0))
        soft = gaussian_filter(accum, sigma=(1.1, 1.1, 0))

        final = plate_bg + soft + glow_layer * 0.35
        final *= vignette
        final = np.clip(final, 0.0, 1.0)

        img = (final * 255.0).astype(np.uint8)
        out_path = os.path.join(frames_dir, f"{f:04d}.png")
        Image.fromarray(img, mode="RGB").save(out_path)

        if f % 30 == 0:
            print(f"Frame {f}/{frames} - Modo: m={m}, n={n}")

    meta = {
        "duration_s": frames / 60.0,
        "fps": 60,
        "events": events_export,
    }
    events_path = os.path.join(repo, "data", f"{args.name}_events.json")
    os.makedirs(os.path.dirname(events_path), exist_ok=True)
    with open(events_path, "w") as fh:
        json.dump(meta, fh)

    print("DONE")


if __name__ == "__main__":
    main()
