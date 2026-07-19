"""
lorenz_attractor.py — Simulación del Atractor de Lorenz (efecto mariposa).

Miles de partículas se advectan siguiendo el sistema caótico de Lorenz, 
comenzando muy juntas y separándose sutilmente a lo largo del tiempo. 
Genera eventos de sonificación cuando el "enjambre" cruza de un ala a otra.
"""

import bpy
import sys
import os
import math
import json
import numpy as np

# --------------------------------------------------------------------------
# 0. Argumentos
# --------------------------------------------------------------------------
argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []

def arg(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default

ENGINE = str(arg("--engine", "eevee")).lower()
FRAMES = int(arg("--frames", 360))
RES_H = int(arg("--res", 360))
FORMAT = str(arg("--format", "16:9"))
if FORMAT == "9:16":
    RES_W = int(RES_H * 9 / 16)
else:
    RES_W = int(RES_H * 16 / 9)
SAMPLES = int(arg("--samples", 32))
FPS = 24
NAME = str(arg("--name", "lorenz"))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

# --------------------------------------------------------------------------
# 1. Parámetros de la simulación
# --------------------------------------------------------------------------
N = 1000             # nº de partículas
TRAIL = 24           # longitud de la estela (frames)
SEED_RADIUS = 0.1    # radio de siembra inicial (muy pequeño para que viajen juntas)
SPEED = 0.4          # escala de tiempo
DT = SPEED / FPS

# Parámetros clásicos de Lorenz
SIGMA = 10.0
RHO = 28.0
BETA = 8.0 / 3.0
SCALE = 0.15         # Escalar para que quepa bien en la vista de Blender (Z va de 0 a 50 normalmente)
OFFSET_Z = -25.0     # Centrar en Z

def velocity(P):
    """Derivadas del atractor de Lorenz."""
    # Desescalar posiciones
    P_real = P / SCALE
    P_real[:, 2] -= OFFSET_Z
    
    x, y, z = P_real[:, 0], P_real[:, 1], P_real[:, 2]
    
    dx = SIGMA * (y - x)
    dy = x * (RHO - z) - y
    dz = x * y - BETA * z
    
    # Escalar velocidad
    v = np.stack([dx, dy, dz], axis=1) * SCALE
    return v

def rk4(P):
    k1 = velocity(P)
    k2 = velocity(P + 0.5 * DT * k1)
    k3 = velocity(P + 0.5 * DT * k2)
    k4 = velocity(P + DT * k3)
    return P + (DT / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

# --------------------------------------------------------------------------
# 2. Simulación y eventos
# --------------------------------------------------------------------------
def simulate():
    rng = np.random.default_rng(42)
    # Sembrar cerca de un punto en el atractor, ej: (1.0, 1.0, 20.0)
    P0 = np.array([1.0, 1.0, 20.0]) * SCALE
    P0[2] += OFFSET_Z * SCALE
    
    P = P0 + rng.normal(size=(N, 3)) * SEED_RADIUS
    positions = np.empty((FRAMES, N, 3), dtype=np.float32)
    
    events = []
    prev_com_x = None

    for f in range(FRAMES):
        positions[f] = P
        
        # Centro de masa del enjambre
        com = np.mean(P, axis=0)
        com_x = com[0]
        
        # Detectar cruce del plano X=0 (cambio de ala de la mariposa)
        if prev_com_x is not None:
            if prev_com_x < 0 and com_x >= 0:
                events.append({
                    "frame": f,
                    "t_seconds": round(f / FPS, 4),
                    "type": "wing_cross",
                    "wing": "right",
                    "note": "G3",
                    "intensity": 0.8
                })
            elif prev_com_x > 0 and com_x <= 0:
                events.append({
                    "frame": f,
                    "t_seconds": round(f / FPS, 4),
                    "type": "wing_cross",
                    "wing": "left",
                    "note": "C3",
                    "intensity": 0.8
                })
        
        prev_com_x = com_x
        P = rk4(P)

    return positions, events

# --------------------------------------------------------------------------
# 3. Escena Blender (mundo oscuro, estelas emisivas, glare, cámara en órbita)
# --------------------------------------------------------------------------
def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

def make_trails():
    curve = bpy.data.curves.new("Trails", type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.015
    curve.bevel_resolution = 0

    mat = bpy.data.materials.new("Glow")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.4, 0.1, 1.0) # Naranja luminoso
    em.inputs["Strength"].default_value = 8.0
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    curve.materials.append(mat)

    obj = bpy.data.objects.new("Trails", curve)
    bpy.context.collection.objects.link(obj)
    return curve

def update_trails(curve, window):
    curve.splines.clear()
    L = window.shape[0]
    for i in range(N):
        sp = curve.splines.new("POLY")
        sp.points.add(L - 1)
        co = np.ones((L, 4), dtype=np.float32)
        co[:, :3] = window[:, i, :]
        sp.points.foreach_set("co", co.ravel())

def setup_scene():
    clear_scene()
    scene = bpy.context.scene

    target = bpy.data.objects.new("Target", None)
    bpy.context.collection.objects.link(target)

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = (0, -10.0, 2.0)
    bpy.context.collection.objects.link(cam)
    con = cam.constraints.new(type="TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    scene.camera = cam

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.01, 0.005, 0.015, 1.0)
    scene.world = world

    scene.use_nodes = True
    ct = scene.node_tree
    ct.nodes.clear()
    rl = ct.nodes.new("CompositorNodeRLayers")
    glare = ct.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "MEDIUM"
    glare.size = 8
    comp = ct.nodes.new("CompositorNodeComposite")
    ct.links.new(rl.outputs["Image"], glare.inputs["Image"])
    ct.links.new(glare.outputs["Image"], comp.inputs["Image"])

    scene.render.resolution_x = RES_W
    scene.render.resolution_y = RES_H
    scene.render.fps = FPS
    scene.render.image_settings.file_format = "PNG"
    
    if ENGINE == "cycles":
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = SAMPLES
        scene.cycles.use_denoising = True
    else:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.eevee.taa_render_samples = SAMPLES

    return cam

def cam_location(f):
    a = math.radians(-60) + math.radians(60) * (f / max(1, FRAMES - 1))
    radius = 21.0 if FORMAT == "9:16" else 11.0
    return (radius * math.cos(a), radius * math.sin(a), 4.0)

# --------------------------------------------------------------------------
# 4. Render
# --------------------------------------------------------------------------
def run():
    print(f"[lorenz] simulando {N} partículas x {FRAMES} frames...")
    positions, events = simulate()
    with open(EVENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "fps": FPS, "frames": FRAMES, "duration_s": round(FRAMES / FPS, 4),
            "resolution": [RES_W, RES_H], "engine": ENGINE, "events": events,
        }, fh, indent=2, ensure_ascii=False)
    print(f"[lorenz] eventos: {len(events)} -> {EVENTS_PATH}")

    cam = setup_scene()
    curve = make_trails()
    scene = bpy.context.scene

    for f in range(FRAMES):
        lo = max(0, f - TRAIL + 1)
        update_trails(curve, positions[lo:f + 1])
        cam.location = cam_location(f)
        scene.frame_set(f)
        scene.render.filepath = os.path.join(FRAMES_DIR, f"{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        if f % 24 == 0 or f == FRAMES - 1:
            print(f"[lorenz] frame {f + 1}/{FRAMES}")

    print("\n[lorenz] ====== RESUMEN ======")
    print(f"[lorenz] motor   : {ENGINE} ({RES_W}x{RES_H}, {SAMPLES} samples)")
    print(f"[lorenz] frames  : {FRAMES} -> {FRAMES_DIR}")
    print(f"[lorenz] eventos : {len(events)} -> {EVENTS_PATH}")


if __name__ == "__main__":
    run()
