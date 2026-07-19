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
parser.add_argument("--name", default="pendulum")
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
N = 1500          # Partículas en el enjambre
TRAIL = 20        # Longitud de estela
FPS = 60
SPEED = 1.0       # Tiempo real
DT = SPEED / FPS
SUBSTEPS = 2      # Sub-pasos para estabilidad numérica
DT_SUB = DT / SUBSTEPS
SCALE = 1.5       # Factor de escala para Blender

# Física del péndulo doble
G_ACC = 9.81
M1, M2 = 1.0, 1.0
L1, L2 = 1.0, 1.0

# Condiciones iniciales (alto potencial => caída dramática)
THETA1_0 = 3 * np.pi / 4     # 135 grados - alto
THETA2_0 = 3 * np.pi / 4     # 135 grados - alto
PERTURBATION = 1e-3           # Perturbación mínima en theta2

# ==============================================================================
# Limpiar escena
# ==============================================================================
bpy.ops.wm.read_factory_settings(use_empty=True)

# ==============================================================================
# Ecuaciones del Péndulo Doble (vectorizadas sobre N partículas)
# ==============================================================================
def derivatives(S):
    """S shape: (N, 4) = [theta1, theta2, omega1, omega2]"""
    t1, t2, w1, w2 = S[:, 0], S[:, 1], S[:, 2], S[:, 3]
    delta = t1 - t2
    cos_d = np.cos(delta)
    sin_d = np.sin(delta)
    den = 3.0 - np.cos(2 * delta)   # = 2*m1 + m2 - m2*cos(2*delta) con m1=m2=1

    alpha1 = (-3.0 * G_ACC * np.sin(t1)
              - G_ACC * np.sin(t1 - 2 * t2)
              - 2.0 * sin_d * (w2**2 + w1**2 * cos_d)) / den

    alpha2 = (2.0 * sin_d * (2 * w1**2
              + 2 * G_ACC * np.cos(t1)
              + w2**2 * cos_d)) / den

    return np.stack([w1, w2, alpha1, alpha2], axis=1)


def rk4_step(S, dt):
    k1 = derivatives(S)
    k2 = derivatives(S + 0.5 * dt * k1)
    k3 = derivatives(S + 0.5 * dt * k2)
    k4 = derivatives(S + dt * k3)
    return S + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


# ==============================================================================
# Simulación completa
# ==============================================================================
def simulate():
    rng = np.random.default_rng(42)

    # Estado inicial: todas las partículas casi idénticas
    S = np.zeros((N, 4), dtype=np.float64)
    S[:, 0] = THETA1_0                                      # theta1 igual
    S[:, 1] = THETA2_0 + rng.normal(0, PERTURBATION, N)     # theta2 con perturbación minúscula
    # omega1 = omega2 = 0 (soltamos desde el reposo)

    # Offsets fijos en Y para dar profundidad 3D al enjambre plano
    y_offsets = np.linspace(-0.06, 0.06, N).astype(np.float32)
    rng.shuffle(y_offsets)

    positions = np.empty((FRAMES, N, 3), dtype=np.float32)
    events = []

    prev_std = 1e-10
    explosion_frame = None

    for f in range(FRAMES):
        t1, t2 = S[:, 0], S[:, 1]

        # Posición de la punta del segundo brazo
        tip_x = L1 * np.sin(t1) + L2 * np.sin(t2)
        tip_y = -L1 * np.cos(t1) - L2 * np.cos(t2)

        # Mapeo 3D: X = tip_x, Y = profundidad fija, Z = tip_y (vertical)
        positions[f, :, 0] = (tip_x * SCALE).astype(np.float32)
        positions[f, :, 1] = y_offsets
        positions[f, :, 2] = (tip_y * SCALE).astype(np.float32)

        # Medir divergencia del enjambre
        std_pos = float(np.std(tip_x) + np.std(tip_y))

        # --- Evento: EXPLOSIÓN PRINCIPAL ---
        if std_pos > 0.05 and explosion_frame is None:
            explosion_frame = f
            events.append({
                "frame": f,
                "t_seconds": round(f / FPS, 4),
                "type": "explosion",
                "intensity": 2.5,
                "note": "C1"
            })

        # --- Eventos: picos de divergencia posteriores ---
        if explosion_frame is not None and f > explosion_frame:
            if std_pos > prev_std * 1.8 and std_pos > 0.15:
                note = str(rng.choice(["Eb2", "G2", "C3", "Eb3"]))
                events.append({
                    "frame": f,
                    "t_seconds": round(f / FPS, 4),
                    "type": "divergence_spike",
                    "intensity": float(min(1.5, std_pos * 0.8)),
                    "note": note
                })

        prev_std = max(std_pos, 1e-10)

        # Integrar (sub-steps para estabilidad)
        for _ in range(SUBSTEPS):
            S = rk4_step(S, DT_SUB)

    return positions, events

print("[pendulum] Simulando enjambre de 1500 péndulos dobles...")
pos_data, events_list = simulate()
print(f"[pendulum] Simulación completa. {len(events_list)} eventos detectados.")

# ==============================================================================
# Construir Curvas (patrón optimizado sin fugas de memoria)
# ==============================================================================
def make_trails():
    curve_data = bpy.data.curves.new('PendulumTrails', type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = 0.006  # Much thinner lines
    curve_data.bevel_resolution = 0

    mat = bpy.data.materials.new("TrailMat")
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    emis = nodes.new("ShaderNodeEmission")
    emis.inputs["Strength"].default_value = 10.0
    links.new(emis.outputs[0], out.inputs["Surface"])

    # Color por altura (Z) → gradiente de temperatura visual
    geom = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geom.outputs["Position"], sep.inputs["Vector"])

    ramp = nodes.new("ShaderNodeValToRGB")
    # Azul profundo (abajo) → Ámbar (medio) → Oro (alto) → Magenta (muy alto)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.0, 0.12, 1.0, 1.0)    # Azul eléctrico
    ramp.color_ramp.elements.new(0.4)
    ramp.color_ramp.elements[1].position = 0.4
    ramp.color_ramp.elements[1].color = (1.0, 0.35, 0.0, 1.0)    # Naranja fuego
    ramp.color_ramp.elements.new(0.7)
    ramp.color_ramp.elements[2].position = 0.7
    ramp.color_ramp.elements[2].color = (1.0, 0.9, 0.15, 1.0)    # Oro brillante
    ramp.color_ramp.elements[3].position = 1.0
    ramp.color_ramp.elements[3].color = (1.0, 0.05, 0.4, 1.0)    # Magenta eléctrico

    map_range = nodes.new("ShaderNodeMapRange")
    map_range.inputs[1].default_value = -3.0   # Min Z (péndulo abajo)
    map_range.inputs[2].default_value = 1.5    # Max Z (péndulo arriba)

    links.new(sep.outputs["Z"], map_range.inputs["Value"])
    links.new(map_range.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], emis.inputs["Color"])

    curve_data.materials.append(mat)

    # Pre-allocate ALL splines (evita fugas de memoria)
    for i in range(N):
        sp = curve_data.splines.new("POLY")
        sp.points.add(TRAIL - 1)

    obj = bpy.data.objects.new('PendulumTrails_Obj', curve_data)
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
bpy.ops.object.camera_add(location=(0, -6, 0))
cam = bpy.context.active_object
cam.data.lens = 28
bpy.context.scene.camera = cam

# Target: centro de la acción del péndulo (ligeramente debajo del pivote)
bpy.ops.object.empty_add(location=(0, 0, -SCALE * 0.5))
target = bpy.context.active_object
tc = cam.constraints.new(type='TRACK_TO')
tc.target = target
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'

# Compositor: Fog Glow para estelas brillantes
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

# Fondo negro profundo
world = bpy.data.worlds.new("World")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.003, 0.003, 0.012, 1.0)
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
# Cámara orbital con oscilación vertical suave
# ==============================================================================
def cam_location(f):
    a = np.radians(30) + np.radians(120) * (f / max(1, FRAMES - 1))
    radius = 5.5 if args.format == "9:16" else 4.5
    z_h = 0.8 + 0.6 * np.sin(f / FRAMES * np.pi * 1.5)
    return (radius * np.cos(a), radius * np.sin(a), z_h)


# ==============================================================================
# Render con soporte de reanudación
# ==============================================================================
curve_data = make_trails()

print(f"[pendulum] Renderizando {FRAMES} frames...")
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
        print(f"[pendulum] frame {f + 1}/{FRAMES}")

print("[blender] DONE")
