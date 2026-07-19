import bpy
import numpy as np
import os
import sys
import argparse
import json
import math

# ==============================================================================
# Parámetros por línea de comandos
# ==============================================================================
parser = argparse.ArgumentParser()
parser.add_argument("--engine", default="eevee")
parser.add_argument("--frames", type=int, default=360)
parser.add_argument("--res", type=int, default=1024)
parser.add_argument("--samples", type=int, default=32)
parser.add_argument("--name", default="thomas")
parser.add_argument("--format", default="16:9")
try:
    idx = sys.argv.index("--")
    args = parser.parse_args(sys.argv[idx+1:])
except ValueError:
    args = parser.parse_args([])

FRAMES = args.frames
RES_H = args.res
RES_W = int(RES_H * 9/16) if args.format == "9:16" else int(RES_H * 16/9)
NAME = args.name

# ==============================================================================
# Parámetros de la simulación
# ==============================================================================
N = 2500
TRAIL = 35
FPS = 60
SPEED = 0.5
DT = SPEED / FPS

B_VAL = 0.208186
SCALE = 0.5

# ==============================================================================
# Limpiar escena
# ==============================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)

# ==============================================================================
# Generar posiciones (Thomas Attractor)
# ==============================================================================
def rk4(P):
    def vel(p):
        pr = p / SCALE
        x, y, z = pr[:, 0], pr[:, 1], pr[:, 2]
        dx = np.sin(y) - B_VAL * x
        dy = np.sin(z) - B_VAL * y
        dz = np.sin(x) - B_VAL * z
        return np.stack([dx, dy, dz], axis=1) * SCALE

    k1 = vel(P)
    k2 = vel(P + 0.5 * DT * k1)
    k3 = vel(P + 0.5 * DT * k2)
    k4 = vel(P + DT * k3)
    return P + (DT / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

def simulate():
    rng = np.random.default_rng(42)
    P0 = np.array([1.0, 1.0, 1.0]) * SCALE
    SEED_RADIUS = 0.1 * SCALE
    P = P0 + rng.normal(size=(N, 3)) * SEED_RADIUS
    
    positions = np.empty((FRAMES, N, 3), dtype=np.float32)
    events = []
    
    prev_com_real_quadrant = None
    
    for f in range(FRAMES):
        positions[f] = P
        
        # Calcular centro de masa real
        com = np.mean(P, axis=0) / SCALE
        # Detectamos un evento cuando el cuadrante predominante cambia (cruzando los ejes del laberinto)
        quadrant = (com > 0).astype(int)
        quad_tuple = tuple(quadrant)
        
        if prev_com_real_quadrant is not None and quad_tuple != prev_com_real_quadrant:
            # Shift in ring / quadrant
            # We add a chime event
            intensity = 0.8 + rng.random() * 0.4
            events.append({
                "frame": f,
                "t_seconds": round(f / FPS, 4),
                "type": "ring_shift",
                "intensity": intensity,
                "note": "C3" if rng.random() > 0.5 else "G3"
            })
            
        prev_com_real_quadrant = quad_tuple
        
        P = rk4(P)
        
    return positions, events

pos_data, events_list = simulate()

# ==============================================================================
# Construir Estructura (Curvas y Material Libre de fugas)
# ==============================================================================
def make_trails():
    curve_data = bpy.data.curves.new('ThomasTrails', type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 0.025
    curve_data.bevel_resolution = 0
    
    mat = bpy.data.materials.new("TrailMat")
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    emis = nodes.new("ShaderNodeEmission")
    emis.inputs["Strength"].default_value = 8.0
    links.new(emis.outputs[0], out.inputs["Surface"])

    info = nodes.new("ShaderNodeObjectInfo")
    math_node = nodes.new("ShaderNodeVectorMath")
    math_node.operation = 'LENGTH'
    
    # We will use the particle's physical position to color
    geom = nodes.new("ShaderNodeNewGeometry")
    links.new(geom.outputs["Position"], math_node.inputs[0])

    ramp = nodes.new("ShaderNodeValToRGB")
    # Cristalino: Celeste -> Turquesa -> Blanco
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.0, 0.4, 1.0, 1.0) # Azul celeste
    ramp.color_ramp.elements.new(0.5)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (0.0, 1.0, 0.8, 1.0) # Turquesa
    ramp.color_ramp.elements[2].position = 1.0
    ramp.color_ramp.elements[2].color = (1.0, 1.0, 1.0, 1.0) # Blanco

    # Map distance
    map_range = nodes.new("ShaderNodeMapRange")
    map_range.inputs[1].default_value = 0.0
    map_range.inputs[2].default_value = 4.0
    
    links.new(math_node.outputs["Value"], map_range.inputs["Value"])
    links.new(map_range.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], emis.inputs["Color"])

    curve_data.materials.append(mat)
    
    # Pre-allocate splines to prevent memory leak
    for i in range(N):
        sp = curve_data.splines.new("POLY")
        sp.points.add(TRAIL - 1)
        
    obj = bpy.data.objects.new('ThomasTrails_Obj', curve_data)
    bpy.context.collection.objects.link(obj)
    return curve_data

def update_trails(curve, window):
    L = window.shape[0]
    if L < TRAIL:
        pad = TRAIL - L
        padded = np.pad(window, ((pad, 0), (0, 0), (0, 0)), mode='edge')
    else:
        padded = window
        
    co = np.ones((TRAIL, 4), dtype=np.float32)
    for i in range(N):
        sp = curve.splines[i]
        co[:, :3] = padded[:, i, :]
        sp.points.foreach_set("co", co.ravel())

# ==============================================================================
# Cámara y Escena
# ==============================================================================
bpy.ops.object.camera_add(location=(0, -4, 2))
cam = bpy.context.active_object
cam.data.lens = 24  # Lente más angular para inmersión
bpy.context.scene.camera = cam

tt = bpy.ops.object.empty_add(location=(0, 0, 0))
target = bpy.context.active_object
tc = cam.constraints.new(type='TRACK_TO')
tc.target = target
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'

scene = bpy.context.scene
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

world = bpy.data.worlds.new("World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.005, 0.005, 0.015, 1.0)
scene.world = world

scene.render.resolution_x = RES_W
scene.render.resolution_y = RES_H
scene.render.fps = FPS
scene.render.image_settings.file_format = "PNG"

if args.engine == 'eevee':
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.eevee.taa_render_samples = args.samples
else:
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True

repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
outdir = os.path.join(repo_dir, "output", NAME, "frames")
os.makedirs(outdir, exist_ok=True)

# Guardar Eventos JSON
events_path = os.path.join(repo_dir, "data", f"{NAME}_events.json")
with open(events_path, "w") as fh:
    json.dump({
        "fps": FPS, "frames": FRAMES, "duration_s": round(FRAMES / FPS, 4),
        "resolution": [RES_W, RES_H], "engine": args.engine, "events": events_list
    }, fh, indent=2)

print(f"\n[blender] Guardado events en: {events_path}")

# Render manual loop
def cam_location(f):
    a = np.radians(45) + np.radians(90) * (f / max(1, FRAMES - 1))
    radius = 3.8 if args.format == "9:16" else 2.5
    # Cámara oscilando verticalmente dentro del atractor
    z_osc = 1.5 * np.sin(f / FRAMES * np.pi * 2)
    return (radius * np.cos(a), radius * np.sin(a), z_osc)

curve_data = make_trails()

print(f"[thomas] Renderizando {FRAMES} frames...")
for f in range(FRAMES):
    lo = max(0, f - TRAIL + 1)
    update_trails(curve_data, pos_data[lo:f + 1])
    cam.location = cam_location(f)
    scene.frame_set(f)
    
    out_path = os.path.join(outdir, f"{f:04d}.png")
    scene.render.filepath = out_path
    
    if not os.path.exists(out_path):
        bpy.ops.render.render(write_still=True)
        
    if f % 24 == 0 or f == FRAMES - 1:
        print(f"[thomas] frame {f + 1}/{FRAMES}")

print("[blender] DONE")
