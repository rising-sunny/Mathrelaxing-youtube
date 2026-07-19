"""
rossler_attractor.py — Simulación del Atractor de Rössler.

Genera eventos de sonificación cuando la partícula hace un "disparo" en el eje Z.
El color de la estela es dinámico y depende de la posición Z (Azul -> Cian -> Rosa).
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
NAME = str(arg("--name", "rossler"))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

# --------------------------------------------------------------------------
# 1. Parámetros de la simulación
# --------------------------------------------------------------------------
N = 1000             # nº de partículas
TRAIL = 30           # longitud de la estela (frames) - un poco más larga para Rössler
SEED_RADIUS = 0.01    # radio de siembra real
SPEED = 0.6          # escala de tiempo (Rössler es un poco más lento que Lorenz visualmente)
DT = SPEED / FPS

# Parámetros clásicos de Rössler
A = 0.2
B = 0.2
C = 5.7
SCALE = 0.25         # Escalar para Blender (Rössler Z max es ~30. 30*0.25 = 7.5)
OFFSET_Z = 0.0

def velocity(P):
    """Derivadas del atractor de Rössler."""
    P_real = P / SCALE
    P_real[:, 2] -= OFFSET_Z
    
    x, y, z = P_real[:, 0], P_real[:, 1], P_real[:, 2]
    
    dx = -y - z
    dy = x + A * y
    dz = B + z * (x - C)
    
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
    # Sembrar en el atractor de Rössler
    P0 = np.array([10.0, 0.0, 0.0]) * SCALE
    P0[2] += OFFSET_Z * SCALE
    
    P = P0 + rng.normal(size=(N, 3)) * (SEED_RADIUS * SCALE)
    positions = np.empty((FRAMES, N, 3), dtype=np.float32)
    
    events = []
    prev_com_z_real = None

    for f in range(FRAMES):
        positions[f] = P
        
        # Centro de masa del enjambre
        com = np.mean(P, axis=0)
        com_z_real = (com[2] / SCALE) - OFFSET_Z
        
        # Detectar "z_spike" cuando la coordenada Z supera los 5.0 hacia arriba
        if prev_com_z_real is not None:
            if prev_com_z_real < 5.0 and com_z_real >= 5.0:
                events.append({
                    "frame": f,
                    "t_seconds": round(f / FPS, 4),
                    "type": "z_spike",
                    "note": "C3",
                    "intensity": 0.9
                })
        
        prev_com_z_real = com_z_real
        P = rk4(P)

    return positions, events

# --------------------------------------------------------------------------
# 3. Escena Blender (Material Dinámico por Z)
# --------------------------------------------------------------------------
def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

def make_trails():
    curve = bpy.data.curves.new("Trails", type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.015
    curve.bevel_resolution = 0

    mat = bpy.data.materials.new("GlowDynamic")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 10.0
    
    # Nodos para Color Dinámico según Z
    geom = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    map_range = nt.nodes.new("ShaderNodeMapRange")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    
    # Z en Blender va de 0 a ~7.5
    map_range.inputs[1].default_value = 0.0 # From Min
    map_range.inputs[2].default_value = 6.0 # From Max
    
    # Colores del Ramp
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.0, 0.1, 1.0, 1.0) # Azul profundo
    
    mid = ramp.color_ramp.elements.new(0.4)
    mid.color = (0.0, 0.8, 1.0, 1.0) # Cian vibrante
    
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (1.0, 0.0, 0.8, 1.0) # Rosa/Magenta en el pico
    
    # Enlaces
    nt.links.new(geom.outputs["Position"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], map_range.inputs["Value"])
    nt.links.new(map_range.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
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
    target.location = (0, 0, 2.0) # Mirar un poco hacia arriba para ver el Z spike
    bpy.context.collection.objects.link(target)

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = (0, -12.0, 6.0)
    bpy.context.collection.objects.link(cam)
    con = cam.constraints.new(type="TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    scene.camera = cam

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.005, 0.01, 0.015, 1.0) # Fondo ligeramente azulado oscuro
    scene.world = world

    scene.use_nodes = True
    ct = scene.node_tree
    ct.nodes.clear()
    rl = ct.nodes.new("CompositorNodeRLayers")
    glare = ct.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "HIGH"
    glare.size = 9
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
    # Rotación lenta de la cámara alrededor de la escena
    a = math.radians(-45) + math.radians(90) * (f / max(1, FRAMES - 1))
    radius = 22.0 if FORMAT == "9:16" else 15.0
    return (radius * math.cos(a), radius * math.sin(a), 6.0)

# --------------------------------------------------------------------------
# 4. Render
# --------------------------------------------------------------------------
def run():
    print(f"[rossler] simulando {N} partículas x {FRAMES} frames...")
    positions, events = simulate()
    with open(EVENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "fps": FPS, "frames": FRAMES, "duration_s": round(FRAMES / FPS, 4),
            "resolution": [RES_W, RES_H], "engine": ENGINE, "events": events,
        }, fh, indent=2, ensure_ascii=False)
    print(f"[rossler] eventos: {len(events)} -> {EVENTS_PATH}")

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
            print(f"[rossler] frame {f + 1}/{FRAMES}")

    print("\n[rossler] ====== RESUMEN ======")
    print(f"[rossler] motor   : {ENGINE} ({RES_W}x{RES_H}, {SAMPLES} samples)")
    print(f"[rossler] frames  : {FRAMES} -> {FRAMES_DIR}")
    print(f"[rossler] eventos : {len(events)} -> {EVENTS_PATH}")


if __name__ == "__main__":
    run()
