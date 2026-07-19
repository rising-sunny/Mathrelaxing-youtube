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
parser.add_argument("--name", default="abc_flow")
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
N = 3500           # Partículas
TRAIL = 40         # Longitud de estela
FPS = 60
SPEED = 0.3        # Velocidad del campo (lento = más orgánico)
DT = SPEED / FPS
SCALE = 2.0        # Factor de escala espacial

# Parámetros del flujo ABC (Arnold-Beltrami-Childress)
A_PARAM = np.sqrt(3)
B_PARAM = np.sqrt(2)
C_PARAM = 1.0

# ==============================================================================
# Limpiar escena
# ==============================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)

# ==============================================================================
# Funciones del flujo ABC (numpy vectorizado para N partículas)
# ==============================================================================
def abc_velocity(pos, t):
    """Arnold-Beltrami-Childress flow: exact solution of Euler equations."""
    x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
    # Make parameters perfectly periodic over the total duration
    t_norm = t / (FRAMES * DT)
    A = A_PARAM * (1.0 + 0.1 * np.sin(2 * np.pi * 3 * t_norm))
    B = B_PARAM * (1.0 + 0.1 * np.cos(2 * np.pi * 2 * t_norm))
    C = C_PARAM * (1.0 + 0.1 * np.sin(2 * np.pi * 1 * t_norm))
    vx = A * np.sin(z) + C * np.cos(y)
    vy = B * np.sin(x) + A * np.cos(z)
    vz = C * np.sin(y) + B * np.cos(x)
    return np.stack([vx, vy, vz], axis=1)


def rk4_step(pos, t, dt):
    """Integración RK4 del campo de velocidad ABC."""
    k1 = abc_velocity(pos, t)
    k2 = abc_velocity(pos + 0.5 * dt * k1, t + 0.5 * dt)
    k3 = abc_velocity(pos + 0.5 * dt * k2, t + 0.5 * dt)
    k4 = abc_velocity(pos + dt * k3, t + dt)
    return pos + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


# ==============================================================================
# Simulación completa
# ==============================================================================
def simulate():
    rng = np.random.default_rng(42)

    # Distribución inicial: uniforme en [0, 2π]³ (ABC es periódico)
    pos = rng.uniform(0, 2 * np.pi, (N, 3)).astype(np.float64)

    positions = np.empty((FRAMES, N, 3), dtype=np.float32)
    speeds = np.empty((FRAMES, N), dtype=np.float32)
    events = []

    prev_mean_speed = 0.0

    for f in range(FRAMES):
        t = f * DT

        # Guardar posiciones (centradas alrededor del origen)
        positions[f] = ((pos - np.pi) * SCALE).astype(np.float32)

        # Calcular velocidad para colorear por speed
        vel = abc_velocity(pos, t)
        spd = np.sqrt(np.sum(vel**2, axis=1))
        speeds[f] = spd.astype(np.float32)
        mean_speed = float(np.mean(spd))

        # Eventos: ráfagas caóticas
        if f > 10 and mean_speed > prev_mean_speed * 1.5 and mean_speed > 0.8:
            note = str(rng.choice(["C3", "D3", "E3", "G3", "A3", "C4", "D4", "E4"]))
            events.append({
                "frame": f,
                "t_seconds": round(f / FPS, 4),
                "type": "chaos_burst",
                "intensity": float(min(1.5, mean_speed * 0.6)),
                "note": note
            })

        prev_mean_speed = mean_speed

        # Integrar
        pos = rk4_step(pos, t, DT)

        # Wrap periódico: ABC es periódico con periodo 2π
        pos = pos % (2 * np.pi)

    return positions, speeds, events

# Cache de simulación: simulate() es determinista (seed 42), así que cacheamos
# las posiciones para que los reinicios tras un crash de Blender no re-simulen.
# BORRAR data/<NAME>_simcache.npz si se cambian N, FRAMES, SPEED u otros parámetros.
_cache = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "data", f"{NAME}_1h_simcache.npz")

def load_or_simulate():
    if os.path.exists(_cache):
        try:
            d = np.load(_cache, allow_pickle=True)
            if d["positions"].shape[0] == FRAMES and d["positions"].shape[1] == N:
                print(f"[abc_flow] Cache de simulación cargado: {_cache}")
                return d["positions"], d["speeds"], list(d["events"])
            print("[abc_flow] Cache con forma distinta; re-simulando.")
        except Exception as e:
            print(f"[abc_flow] Cache ilegible ({e}); re-simulando.")
    print("[abc_flow] Simulando 5000 partículas en campo ABC flow 3D...")
    p, s, ev = simulate()
    os.makedirs(os.path.dirname(_cache), exist_ok=True)
    np.savez_compressed(_cache, positions=p, speeds=s, events=np.array(ev, dtype=object))
    print(f"[abc_flow] Simulación completa y cacheada ({len(ev)} eventos).")
    return p, s, ev

pos_data, speed_data, events_list = load_or_simulate()
print(f"[abc_flow] {len(events_list)} eventos detectados.")


# ==============================================================================
# Construir Curvas (patrón optimizado sin fugas de memoria)
# ==============================================================================
def make_trails():
    curve_data = bpy.data.curves.new('ABCTrails', type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 0.004  # Líneas más finas para más partículas
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

    # Color por posición → gradiente arcoíris (X + Y + Z combinados)
    geom = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geom.outputs["Position"], sep.inputs["Vector"])

    # Sumar X + Y + Z con dos nodos ADD
    math_add1 = nodes.new("ShaderNodeMath")
    math_add1.operation = 'ADD'
    links.new(sep.outputs["X"], math_add1.inputs[0])
    links.new(sep.outputs["Y"], math_add1.inputs[1])

    math_add2 = nodes.new("ShaderNodeMath")
    math_add2.operation = 'ADD'
    links.new(math_add1.outputs[0], math_add2.inputs[0])
    links.new(sep.outputs["Z"], math_add2.inputs[1])

    ramp = nodes.new("ShaderNodeValToRGB")
    # Arcoíris completo: Violeta → Azul → Cyan → Verde → Amarillo → Magenta
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.4, 0.0, 0.8, 1.0)      # Deep Violet
    ramp.color_ramp.elements.new(0.2)
    ramp.color_ramp.elements[1].position = 0.2
    ramp.color_ramp.elements[1].color = (0.0, 0.3, 1.0, 1.0)      # Electric Blue
    ramp.color_ramp.elements.new(0.4)
    ramp.color_ramp.elements[2].position = 0.4
    ramp.color_ramp.elements[2].color = (0.0, 0.8, 0.9, 1.0)      # Cyan
    ramp.color_ramp.elements.new(0.6)
    ramp.color_ramp.elements[3].position = 0.6
    ramp.color_ramp.elements[3].color = (0.1, 0.9, 0.3, 1.0)      # Emerald Green
    ramp.color_ramp.elements.new(0.8)
    ramp.color_ramp.elements[4].position = 0.8
    ramp.color_ramp.elements[4].color = (1.0, 0.85, 0.1, 1.0)     # Golden Yellow
    ramp.color_ramp.elements[5].position = 1.0
    ramp.color_ramp.elements[5].color = (1.0, 0.1, 0.5, 1.0)      # Hot Magenta

    map_range = nodes.new("ShaderNodeMapRange")
    map_range.inputs[1].default_value = -8.0   # Min combinado
    map_range.inputs[2].default_value = 8.0    # Max combinado

    links.new(math_add2.outputs[0], map_range.inputs["Value"])
    links.new(map_range.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], emis.inputs["Color"])

    curve_data.materials.append(mat)

    # Pre-allocate ALL splines
    for i in range(N):
        sp = curve_data.splines.new("POLY")
        sp.points.add(TRAIL - 1)

    obj = bpy.data.objects.new('ABCTrails_Obj', curve_data)
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
# Cámara, Compositor y Escena
# ==============================================================================
bpy.ops.object.camera_add(location=(0, -8, 3))
cam = bpy.context.active_object
cam.data.lens = 32
bpy.context.scene.camera = cam

# Target: centro del campo
bpy.ops.object.empty_add(location=(0, 0, 0))
target = bpy.context.active_object
tc = cam.constraints.new(type='TRACK_TO')
tc.target = target
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'

# Compositor: Fog Glow
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

# Fondo oscuro azul-violeta
world = bpy.data.worlds.new("World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.003, 0.002, 0.012, 1.0)
scene.world = world

# Resolución y render
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


# ==============================================================================
# Cámara orbital suave
# ==============================================================================
def cam_location(f):
    progress = f / max(1, FRAMES)
    a = np.radians(360) * progress  # Órbita completa 360° exacta (sin el -1 para loop)
    radius = 9.0 if args.format == "9:16" else 7.5
    z_h = 1.0 + 3.0 * np.sin(2 * np.pi * 2 * progress)  # Oscilación vertical (2 ciclos)
    return (radius * np.cos(a), radius * np.sin(a), z_h)


# ==============================================================================
# Render con soporte de reanudación
# ==============================================================================
curve_data = make_trails()

print(f"[abc_flow] Renderizando {FRAMES} frames...")
for f in range(FRAMES):
    out_path = os.path.join(outdir, f"{f:04d}.png")
    if os.path.exists(out_path):
        continue

    lo = max(0, f - TRAIL + 1)
    update_trails(curve_data, pos_data[lo:f + 1])
    cam.location = cam_location(f)
    scene.frame_set(f)

    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

    if f % 24 == 0 or f == FRAMES - 1:
        print(f"[abc_flow] frame {f + 1}/{FRAMES}")

print("[blender] DONE")
