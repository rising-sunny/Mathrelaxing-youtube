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
parser.add_argument("--frames", type=int, default=900)
parser.add_argument("--res", type=int, default=1024)
parser.add_argument("--samples", type=int, default=32)
parser.add_argument("--name", default="tokamak_flow")
parser.add_argument("--format", default="9:16")
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
N = 3500           # Partículas
TRAIL = 40         # Longitud de estela
FPS = 60
SPEED = 0.5
DT = SPEED / FPS
R0 = 3.0
MINOR_R = 1.0

# ==============================================================================
# Limpiar escena
# ==============================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)

# ==============================================================================
# Funciones del flujo Tokamak
# ==============================================================================
def tokamak_velocity(pos, B_toroidal=1.0, B_poloidal=0.3):
    x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
    rho = np.sqrt(x**2 + y**2) + 1e-5
    
    phi_x = -y / rho
    phi_y = x / rho
    phi_z = np.zeros_like(x)
    
    r_core_x = x * (1 - R0 / rho)
    r_core_y = y * (1 - R0 / rho)
    r_core_z = z
    
    pol_x = phi_y * r_core_z - phi_z * r_core_y
    pol_y = phi_z * r_core_x - phi_x * r_core_z
    pol_z = phi_x * r_core_y - phi_y * r_core_x
    
    pol_mag = np.sqrt(pol_x**2 + pol_y**2 + pol_z**2) + 1e-5
    pol_x /= pol_mag
    pol_y /= pol_mag
    pol_z /= pol_mag
    
    vx = B_toroidal * phi_x + B_poloidal * pol_x
    vy = B_toroidal * phi_y + B_poloidal * pol_y
    vz = B_toroidal * phi_z + B_poloidal * pol_z
    
    return np.stack([vx, vy, vz], axis=1)

def rk4_step(pos, dt):
    k1 = tokamak_velocity(pos)
    k2 = tokamak_velocity(pos + 0.5 * dt * k1)
    k3 = tokamak_velocity(pos + 0.5 * dt * k2)
    k4 = tokamak_velocity(pos + dt * k3)
    return pos + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

# ==============================================================================
# Simulación completa
# ==============================================================================
def simulate():
    rng = np.random.default_rng(42)

    theta = rng.uniform(0, 2*np.pi, N)
    phi = rng.uniform(0, 2*np.pi, N)
    r = rng.uniform(0.1, MINOR_R, N)
    
    pos = np.zeros((N, 3), dtype=np.float64)
    pos[:, 0] = (R0 + r * np.cos(phi)) * np.cos(theta)
    pos[:, 1] = (R0 + r * np.cos(phi)) * np.sin(theta)
    pos[:, 2] = r * np.sin(phi)

    positions = np.empty((FRAMES, N, 3), dtype=np.float32)
    speeds = np.empty((FRAMES, N), dtype=np.float32)
    events = []

    prev_mean_speed = 0.0

    for f in range(FRAMES):
        positions[f] = pos.astype(np.float32)

        vel = tokamak_velocity(pos)
        spd = np.sqrt(np.sum(vel**2, axis=1))
        speeds[f] = spd.astype(np.float32)
        mean_speed = float(np.mean(spd))

        if f > 10 and mean_speed > prev_mean_speed * 1.05 and mean_speed > 0.5:
            note = str(rng.choice(["C4", "D4", "E4", "G4", "A4", "C5"]))
            events.append({
                "frame": f,
                "t_seconds": round(f / FPS, 4),
                "type": "plasma_burst",
                "intensity": float(min(1.5, mean_speed * 0.8)),
                "note": note
            })

        prev_mean_speed = mean_speed
        pos = rk4_step(pos, DT)

    return positions, speeds, events

_cache = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "data", f"{NAME}_simcache.npz")

def load_or_simulate():
    if os.path.exists(_cache):
        try:
            d = np.load(_cache, allow_pickle=True)
            if d["positions"].shape[0] == FRAMES and d["positions"].shape[1] == N:
                print(f"[tokamak_flow] Cache de simulación cargado: {_cache}")
                return d["positions"], d["speeds"], list(d["events"])
            print("[tokamak_flow] Cache con forma distinta; re-simulando.")
        except Exception as e:
            print(f"[tokamak_flow] Cache ilegible ({e}); re-simulando.")
    print("[tokamak_flow] Simulando...")
    p, s, ev = simulate()
    os.makedirs(os.path.dirname(_cache), exist_ok=True)
    np.savez_compressed(_cache, positions=p, speeds=s, events=np.array(ev, dtype=object))
    print(f"[tokamak_flow] Simulación completa y cacheada ({len(ev)} eventos).")
    return p, s, ev

pos_data, speed_data, events_list = load_or_simulate()
print(f"[tokamak_flow] {len(events_list)} eventos detectados.")

# ==============================================================================
# Construir Curvas
# ==============================================================================
def make_trails():
    curve_data = bpy.data.curves.new('TokamakTrails', type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 0.005
    curve_data.bevel_resolution = 0

    mat = bpy.data.materials.new("TrailMat")
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    emis = nodes.new("ShaderNodeEmission")
    emis.inputs["Strength"].default_value = 12.0
    links.new(emis.outputs[0], out.inputs["Surface"])

    info = nodes.new("ShaderNodeObjectInfo")
    ramp = nodes.new("ShaderNodeValToRGB")
    
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.02, 0.0, 0.2, 1.0)
    ramp.color_ramp.elements.new(0.3)
    ramp.color_ramp.elements[1].position = 0.3
    ramp.color_ramp.elements[1].color = (0.0, 0.1, 0.8, 1.0)
    ramp.color_ramp.elements.new(0.6)
    ramp.color_ramp.elements[2].position = 0.6
    ramp.color_ramp.elements[2].color = (0.0, 0.8, 0.9, 1.0)
    ramp.color_ramp.elements.new(0.8)
    ramp.color_ramp.elements[3].position = 0.8
    ramp.color_ramp.elements[3].color = (0.9, 0.9, 1.0, 1.0)
    ramp.color_ramp.elements.new(1.0)
    ramp.color_ramp.elements[4].position = 1.0
    ramp.color_ramp.elements[4].color = (1.0, 1.0, 1.0, 1.0)

    links.new(info.outputs['Random'], ramp.inputs['Fac'])
    links.new(ramp.outputs["Color"], emis.inputs["Color"])

    curve_data.materials.append(mat)

    for i in range(N):
        sp = curve_data.splines.new("POLY")
        sp.points.add(TRAIL - 1)

    obj = bpy.data.objects.new('TokamakTrails_Obj', curve_data)
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
    curve.update_tag()

# ==============================================================================
# Cámara y Escena
# ==============================================================================
bpy.ops.object.camera_add(location=(0, -9, 0))
cam = bpy.context.active_object
cam.data.lens = 32
bpy.context.scene.camera = cam

bpy.ops.object.empty_add(location=(0, 0, 0))
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
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.001, 0.001, 0.003, 1.0)
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

events_path = os.path.join(repo_dir, "data", f"{NAME}_events.json")
with open(events_path, "w") as fh:
    json.dump({
        "fps": FPS, "frames": FRAMES, "duration_s": round(FRAMES / FPS, 4),
        "resolution": [RES_W, RES_H], "engine": args.engine, "events": events_list
    }, fh, indent=2)

print(f"\n[blender] Guardado events en: {events_path}")

def cam_location(f):
    progress = f / max(1, FRAMES - 1)
    a = np.radians(360) * progress
    radius = 9.0 
    z_h = 4.0 * np.sin(progress * np.pi * 2) 
    return (radius * np.cos(a), radius * np.sin(a), z_h)

curve_data = make_trails()
print(f"[tokamak_flow] Renderizando {FRAMES} frames...")
for f in range(FRAMES):
    out_path = os.path.join(outdir, f"{f:04d}.png")
    if os.path.exists(out_path):
        continue

    lo = max(0, f - TRAIL + 1)
    update_trails(curve_data, pos_data[lo:f + 1])
    cam.location = cam_location(f)
    scene.frame_set(f)

    scene.render.filepath = out_path
    bpy.context.view_layer.update()
    bpy.ops.render.render(write_still=True)

    if f % 24 == 0 or f == FRAMES - 1:
        print(f"[tokamak_flow] frame {f + 1}/{FRAMES}")

print("[blender] DONE")
