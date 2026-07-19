"""
slice_field.py — Vertical slice del pipeline MathRelaxing.

Construye una superficie paramétrica que EVOLUCIONA (sin loop) sobre N frames,
exporta los eventos de geometría a JSON (base de la sonificación) y renderiza
los frames en modo headless.

Ejecutar SIEMPRE vía Blender (nunca importar como módulo):

    blender --background --python scenes/slice_field.py -- --engine cycles --frames 72 --res 360 --samples 24

Args tras `--`:
    --engine   cycles | eevee   (default: cycles, CPU — fiable en headless)
    --frames   nº de frames     (default: 72  → 3 s @ 24 fps)
    --res      altura en px      (default: 360 → 640x360, 16:9)
    --samples  muestras de render(default: 24)
"""

import bpy
import sys
import os
import math
import json

# --------------------------------------------------------------------------
# 0. Argumentos (lo que va después de `--` en la línea de comandos)
# --------------------------------------------------------------------------
argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []


def arg(flag, default):
    return argv[argv.index(flag) + 1] if flag in argv else default


ENGINE = str(arg("--engine", "cycles")).lower()
FRAMES = int(arg("--frames", 72))
RES_H = int(arg("--res", 360))
RES_W = int(RES_H * 16 / 9)
SAMPLES = int(arg("--samples", 24))
FPS = 24

# Raíz del repo = carpeta padre de scenes/
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", "slice", "frames")
EVENTS_PATH = os.path.join(REPO, "data", "slice_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

# --------------------------------------------------------------------------
# 1. Matemática de la evolución (la "física" del slice)
# --------------------------------------------------------------------------
GRID_N = 64          # vértices por lado
GRID_SIZE = 4.0      # tamaño en metros de Blender
EVENT_LEVELS = [0.4, 0.8, 1.2]   # cruces de amplitud que disparan sonificación


def amplitude(t):
    """Amplitud global, crecimiento monótono suave (ease-in) t∈[0,1] -> [0, 1.5].

    El movimiento de la superficie viene de las fases en surface_z; aquí solo
    'construimos' la intensidad de forma majestuosa y SIN retrocesos, para que
    los eventos de sonificación queden bien repartidos en el tiempo."""
    s = t * t * (3.0 - 2.0 * t)   # smoothstep
    return 1.5 * s


def surface_z(x, y, A, t):
    """Altura de la superficie en (x, y) para amplitud A y tiempo t."""
    k = 2.2
    return A * math.sin(k * x + 2 * math.pi * t) * math.cos(k * y + math.pi * t)


# --------------------------------------------------------------------------
# 2. Construcción de la escena (limpia desde cero)
# --------------------------------------------------------------------------
def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def build_grid():
    """Crea la malla-rejilla y devuelve (objeto, lista de (x,y) base por vértice)."""
    verts, base_xy, faces = [], [], []
    for j in range(GRID_N):
        for i in range(GRID_N):
            x = (i / (GRID_N - 1) - 0.5) * GRID_SIZE
            y = (j / (GRID_N - 1) - 0.5) * GRID_SIZE
            verts.append((x, y, 0.0))
            base_xy.append((x, y))
    for j in range(GRID_N - 1):
        for i in range(GRID_N - 1):
            a = j * GRID_N + i
            faces.append((a, a + 1, a + GRID_N + 1, a + GRID_N))

    mesh = bpy.data.meshes.new("FieldMesh")
    mesh.from_pydata(verts, [], faces)
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.update()

    obj = bpy.data.objects.new("Field", mesh)
    bpy.context.collection.objects.link(obj)

    mat = bpy.data.materials.new("FieldMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.02, 0.05, 0.12, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.6
    bsdf.inputs["Roughness"].default_value = 0.35
    obj.data.materials.append(mat)
    return obj, base_xy


def setup_camera_light_world():
    # Cámara con target en el origen (Track To) para encuadre robusto.
    target = bpy.data.objects.new("Target", None)
    bpy.context.collection.objects.link(target)

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = (0.0, -7.0, 4.5)
    bpy.context.collection.objects.link(cam)
    con = cam.constraints.new(type="TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("Key", type="AREA")
    light_data.energy = 600.0
    light_data.size = 6.0
    light = bpy.data.objects.new("Key", light_data)
    light.location = (-4.0, -3.0, 7.0)
    bpy.context.collection.objects.link(light)

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.005, 0.006, 0.012, 1.0)
    bpy.context.scene.world = world


def setup_render():
    scene = bpy.context.scene
    scene.render.resolution_x = RES_W
    scene.render.resolution_y = RES_H
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.render.image_settings.file_format = "PNG"
    if ENGINE == "eevee":
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.eevee.taa_render_samples = SAMPLES
    else:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = SAMPLES
        scene.cycles.use_denoising = True


# --------------------------------------------------------------------------
# 3. Bucle de evolución + render + detección de eventos
# --------------------------------------------------------------------------
def deform(obj, base_xy, A, t):
    z = obj.data.vertices
    for idx, (x, y) in enumerate(base_xy):
        z[idx].co.z = surface_z(x, y, A, t)
    obj.data.update()


def run():
    clear_scene()
    obj, base_xy = build_grid()
    setup_camera_light_world()
    setup_render()
    scene = bpy.context.scene

    events = []
    prev_A = amplitude(0.0)
    fired = set()

    for f in range(FRAMES):
        t = f / (FRAMES - 1)
        A = amplitude(t)
        deform(obj, base_xy, A, t)

        # Detección de eventos: cruce ascendente de cada nivel de amplitud.
        for lvl in EVENT_LEVELS:
            if lvl not in fired and prev_A < lvl <= A:
                events.append({
                    "frame": f,
                    "t_seconds": round(f / FPS, 4),
                    "type": "amplitude_crossing",
                    "level": lvl,
                    "amplitude": round(A, 4),
                })
                fired.add(lvl)
        prev_A = A

        scene.frame_set(f)
        scene.render.filepath = os.path.join(FRAMES_DIR, f"{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[slice] frame {f + 1}/{FRAMES}  t={t:.3f}  A={A:.3f}")

    payload = {
        "fps": FPS,
        "frames": FRAMES,
        "duration_s": round(FRAMES / FPS, 4),
        "resolution": [RES_W, RES_H],
        "engine": ENGINE,
        "events": events,
    }
    with open(EVENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    print("\n[slice] ====== RESUMEN ======")
    print(f"[slice] motor      : {ENGINE}  ({RES_W}x{RES_H}, {SAMPLES} samples)")
    print(f"[slice] frames      : {FRAMES} -> {FRAMES_DIR}")
    print(f"[slice] eventos     : {len(events)} -> {EVENTS_PATH}")


if __name__ == "__main__":
    run()
