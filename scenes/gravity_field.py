import bpy
import numpy as np
import os
import sys
import argparse
import json

# ==============================================================================
# Parámetros por línea de comandos
# ==============================================================================
parser = argparse.ArgumentParser()
parser.add_argument("--engine", default="eevee")
parser.add_argument("--frames", type=int, default=360)
parser.add_argument("--res", type=int, default=1024)
parser.add_argument("--samples", type=int, default=32)
parser.add_argument("--name", default="gravity_field")
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
N = 1000
TRAIL = 20
FPS = 60
SPEED = 1.0
DT = SPEED / FPS

SCALE = 0.5
M_pos = np.array([
    [5.0, 5.0, 0.0],
    [-5.0, 5.0, 0.0],
    [0.0, -5.0, 0.0]
]) * SCALE
M_mass = np.array([150.0, 150.0, 150.0]) * SCALE
P0 = np.array([0.0, 0.0, 5.0]) * SCALE
SEED_RADIUS = 2.0 * SCALE

# ==============================================================================
# Limpiar escena
# ==============================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)

# ==============================================================================
# Generar posiciones (Gravedad N-Body)
# ==============================================================================
def simulate():
    rng = np.random.default_rng(42)
    P_pos = P0 + rng.normal(size=(N, 3)) * SEED_RADIUS
    P_vel = rng.normal(size=(N, 3)) * (1.0 * SCALE)
    
    positions = np.empty((FRAMES, N, 3), dtype=np.float32)
    velocities = np.empty((FRAMES, N, 3), dtype=np.float32)
    
    events = []
    prev_com_v_mag = 0.0
    
    for f in range(FRAMES):
        positions[f] = P_pos
        velocities[f] = P_vel
        
        # Calcular centro de masa y velocidad
        com_pos = np.nanmean(P_pos, axis=0) / SCALE
        com_vel = np.nanmean(P_vel, axis=0) / SCALE
        v_mag = np.linalg.norm(com_vel)
        
        # Evento Slingshot: si la aceleracion es muy grande (v_mag sube rápido)
        if prev_com_v_mag < 2.0 and v_mag >= 2.0:
            events.append({
                "frame": f,
                "t_seconds": round(f / FPS, 4),
                "type": "slingshot",
                "intensity": float((v_mag - 2.0) / 5.0 + 1.0),
                "note": "Eb1" if rng.random() > 0.5 else "G1"
            })
            
        prev_com_v_mag = v_mag
        
        # Integrador de Verlet básico
        acc = np.zeros_like(P_pos)
        for j in range(3):
            r_vec = M_pos[j] - P_pos
            r_sq = np.sum(r_vec**2, axis=1, keepdims=True)
            r_mag = np.sqrt(r_sq + 1.0 * SCALE)
            acc += (M_mass[j] / (r_mag**3)) * r_vec
        acc -= 0.1 * P_vel # Fricción
        
        P_vel += acc * DT
        P_pos += P_vel * DT
        
    return positions, velocities, events

pos_data, vel_data, events_list = simulate()

# ==============================================================================
# Construir Estructura (Curvas y Material)
# ==============================================================================
def make_trails():
    curve_data = bpy.data.curves.new('GravityTrails', type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 0.015
    curve_data.bevel_resolution = 0
    
    mat = bpy.data.materials.new("TrailMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    emis = nodes.new("ShaderNodeEmission")
    emis.inputs["Strength"].default_value = 5.0
    links.new(emis.outputs[0], out.inputs["Surface"])

    info = nodes.new("ShaderNodeObjectInfo")
    math_node = nodes.new("ShaderNodeVectorMath")
    math_node.operation = 'LENGTH'
    
    # We will use the particle's physical position (from Geometry node) to color
    geom = nodes.new("ShaderNodeNewGeometry")
    links.new(geom.outputs["Position"], math_node.inputs[0])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (1.0, 0.8, 0.1, 1.0) # Amarillo intenso
    ramp.color_ramp.elements.new(0.5)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (0.8, 0.2, 0.8, 1.0) # Magenta/Morado
    ramp.color_ramp.elements[2].position = 1.0
    ramp.color_ramp.elements[2].color = (0.0, 0.1, 0.5, 1.0) # Azul oscuro

    # Map distance 0 to 10
    map_range = nodes.new("ShaderNodeMapRange")
    map_range.inputs[1].default_value = 0.0
    map_range.inputs[2].default_value = 8.0
    
    links.new(math_node.outputs["Value"], map_range.inputs["Value"])
    links.new(map_range.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], emis.inputs["Color"])

    curve_data.materials.append(mat)
    
    for i in range(N):
        sp = curve_data.splines.new("POLY")
        sp.points.add(TRAIL - 1)
    
    obj = bpy.data.objects.new('GravityTrails_Obj', curve_data)
    bpy.context.collection.objects.link(obj)
    return curve_data

def update_trails(curve, window):
    L = window.shape[0]
    if L < TRAIL:
        pad = TRAIL - L
        padded = np.pad(window, ((pad, 0), (0, 0), (0, 0)), mode='edge')
    else:
        padded = window
        
    for i in range(N):
        sp = curve.splines[i]
        co = np.ones((TRAIL, 4), dtype=np.float32)
        co[:, :3] = padded[:, i, :]
        sp.points.foreach_set("co", co.ravel())

# ==============================================================================
# Masas Pesadas (Cuerpos)
# ==============================================================================
for i, m_p in enumerate(M_pos):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=m_p)
    bh = bpy.context.active_object
    bh.name = f"BlackHole_{i}"
    
    bh_mat = bpy.data.materials.new(f"BH_Mat_{i}")
    bh_mat.use_nodes = True
    bh_nodes = bh_mat.node_tree.nodes
    bh_nodes.clear()
    bh_out = bh_nodes.new("ShaderNodeOutputMaterial")
    bh_emis = bh_nodes.new("ShaderNodeEmission")
    bh_emis.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    bh_emis.inputs["Strength"].default_value = 0.0
    bh_mat.node_tree.links.new(bh_emis.outputs[0], bh_out.inputs["Surface"])
    bh.data.materials.append(bh_mat)

# ==============================================================================
# Cámara y Escena
# ==============================================================================
bpy.ops.object.camera_add(location=(0, -12, 10))
cam = bpy.context.active_object
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
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.005, 0.005, 0.01, 1.0)
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
    radius = 20.0 if args.format == "9:16" else 15.0
    return (radius * np.cos(a), radius * np.sin(a), 8.0)

curve_data = make_trails()

print(f"[gravity] Renderizando {FRAMES} frames...")
for f in range(FRAMES):
    lo = max(0, f - TRAIL + 1)
    update_trails(curve_data, pos_data[lo:f + 1])
    cam.location = cam_location(f)
    scene.frame_set(f)
    
    # Solo renderizar si el frame no existe (Resume support)
    out_path = os.path.join(outdir, f"{f:04d}.png")
    scene.render.filepath = out_path
    
    if not os.path.exists(out_path):
        bpy.ops.render.render(write_still=True)
        
    if f % 24 == 0 or f == FRAMES - 1:
        print(f"[gravity] frame {f + 1}/{FRAMES}")

print("[blender] DONE")
