"""
flow_field.py — Campo vectorial / flujo (primer fenómeno "real" de MathRelaxing).

Un campo de velocidad incompresible (curl de un potencial = "curl noise") con
varios VÓRTICES analíticos. Miles de partículas se advectan por integración
numérica RK4 y dejan estelas luminosas. Los EVENTOS de sonificación se disparan
en el frame de máxima "actividad" de cada vórtice (cuando el enjambre lo enciende).

Ejecutar SIEMPRE vía Blender:

    blender --background --python scenes/flow_field.py -- --engine eevee --frames 360 --res 360 --samples 32

Args tras `--`:
    --engine   eevee | cycles   (default: eevee)
    --frames   nº de frames      (default: 360 → 15 s @ 24 fps)
    --res      altura en px      (default: 360 → 640x360)
    --samples  muestras          (default: 32)
    --name     subcarpeta/salida (default: flow)
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
RES_W = int(RES_H * 16 / 9)
SAMPLES = int(arg("--samples", 32))
FPS = 24
NAME = str(arg("--name", "flow"))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(REPO, "output", NAME, "frames")
EVENTS_PATH = os.path.join(REPO, "data", f"{NAME}_events.json")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_PATH), exist_ok=True)

# --------------------------------------------------------------------------
# 1. Parámetros de la simulación
# --------------------------------------------------------------------------
N = 1100             # nº de partículas
TRAIL = 18           # longitud de la estela (frames)
SEED_RADIUS = 3.2    # radio de siembra inicial
BOUND = 7.5          # más allá de esto, la partícula reaparece
SPEED = 1.5          # escala global de velocidad
DT = SPEED / FPS
CORE = 0.5           # suavizado del núcleo del vórtice (evita la singularidad dura)

# Vórtices: (centro, eje de giro (unitario), fuerza, nota de sonificación)
def _u(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


VORTICES = [
    (np.array([1.7, 0.0, 0.6]),  _u([0.2, 0.3, 1.0]), 2.3, "C2"),
    (np.array([-1.9, 0.5, -0.3]), _u([0.0, 1.0, 0.2]), 2.0, "Eb2"),
    (np.array([0.2, -1.8, 0.5]),  _u([1.0, 0.1, 0.3]), 1.8, "G2"),
]


def rand_in_sphere(rng, n, R):
    v = rng.normal(size=(n, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    r = R * rng.random(n) ** (1.0 / 3.0)
    return v * r[:, None]


def potential(P):
    """Potencial vectorial suave (curl noise analítico)."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    return np.stack([
        np.sin(0.9 * y + 1.3) * np.cos(0.7 * z),
        np.sin(0.8 * z + 2.1) * np.cos(0.6 * x),
        np.sin(0.7 * x + 0.5) * np.cos(0.9 * y),
    ], axis=1)


def curl(P, eps=1e-3):
    ex = np.array([eps, 0, 0]); ey = np.array([0, eps, 0]); ez = np.array([0, 0, eps])
    dAdx = (potential(P + ex) - potential(P - ex)) / (2 * eps)
    dAdy = (potential(P + ey) - potential(P - ey)) / (2 * eps)
    dAdz = (potential(P + ez) - potential(P - ez)) / (2 * eps)
    return np.stack([
        dAdy[:, 2] - dAdz[:, 1],
        dAdz[:, 0] - dAdx[:, 2],
        dAdx[:, 1] - dAdy[:, 0],
    ], axis=1)


def velocity(P):
    v = 1.5 * curl(P)
    for c, axis, k, _ in VORTICES:
        r = P - c
        cr = np.cross(np.broadcast_to(axis, P.shape), r)
        denom = np.sum(r * r, axis=1, keepdims=True) + CORE * CORE
        v += k * cr / denom
    return v


def rk4(P):
    k1 = velocity(P)
    k2 = velocity(P + 0.5 * DT * k1)
    k3 = velocity(P + 0.5 * DT * k2)
    k4 = velocity(P + DT * k3)
    return P + (DT / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


# --------------------------------------------------------------------------
# 2. Simulación completa (pre-pase, sin render) + detección de eventos
# --------------------------------------------------------------------------
def simulate():
    rng = np.random.default_rng(7)
    P = rand_in_sphere(rng, N, SEED_RADIUS)
    positions = np.empty((FRAMES, N, 3), dtype=np.float32)
    activity = np.zeros((FRAMES, len(VORTICES)))

    for f in range(FRAMES):
        positions[f] = P
        spd = np.linalg.norm(velocity(P), axis=1)
        for vi, (c, _, _, _) in enumerate(VORTICES):
            d2 = np.sum((P - c) ** 2, axis=1)
            activity[f, vi] = np.sum(spd * np.exp(-d2 / (1.3 ** 2)))
        P = rk4(P)
        far = np.linalg.norm(P, axis=1) > BOUND
        if far.any():
            P[far] = rand_in_sphere(rng, int(far.sum()), SEED_RADIUS)

    # Un evento por vórtice, en su frame de máxima actividad.
    peaks = activity.max(axis=0)
    norm = peaks / peaks.max()
    events = []
    for vi, (_, _, _, note) in enumerate(VORTICES):
        f = int(np.argmax(activity[:, vi]))
        events.append({
            "frame": f,
            "t_seconds": round(f / FPS, 4),
            "type": "vortex_peak",
            "vortex": vi,
            "note": note,
            "intensity": round(float(0.6 + 0.4 * norm[vi]), 4),
        })
    events.sort(key=lambda e: e["frame"])
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
    curve.bevel_depth = 0.012
    curve.bevel_resolution = 0

    mat = bpy.data.materials.new("Glow")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.32, 0.62, 1.0, 1.0)
    em.inputs["Strength"].default_value = 5.5
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    curve.materials.append(mat)

    obj = bpy.data.objects.new("Trails", curve)
    bpy.context.collection.objects.link(obj)
    return curve


def update_trails(curve, window):
    """window: array (L, N, 3) con las últimas L posiciones."""
    curve.splines.clear()
    L = window.shape[0]
    for i in range(N):
        sp = curve.splines.new("POLY")
        sp.points.add(L - 1)
        co = np.ones((L, 4), dtype=np.float32)
        co[:, :3] = window[:, i, :]
        sp.points.foreach_set("co", co.ravel())


def cam_location(f):
    a = math.radians(-90) + math.radians(25) * (f / max(1, FRAMES - 1))
    return (9.0 * math.cos(a), 9.0 * math.sin(a), 3.2)


def setup_scene():
    clear_scene()
    scene = bpy.context.scene

    target = bpy.data.objects.new("Target", None)
    bpy.context.collection.objects.link(target)

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.collection.objects.link(cam)
    con = cam.constraints.new(type="TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    scene.camera = cam

    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.005, 0.01, 1.0)
    scene.world = world

    # Compositor: glare Fog Glow para el "bloom" cósmico.
    scene.use_nodes = True
    ct = scene.node_tree
    ct.nodes.clear()
    rl = ct.nodes.new("CompositorNodeRLayers")
    glare = ct.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "MEDIUM"
    glare.size = 7
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


# --------------------------------------------------------------------------
# 4. Render
# --------------------------------------------------------------------------
def run():
    print(f"[flow] simulando {N} partículas x {FRAMES} frames...")
    positions, events = simulate()
    with open(EVENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump({
            "fps": FPS, "frames": FRAMES, "duration_s": round(FRAMES / FPS, 4),
            "resolution": [RES_W, RES_H], "engine": ENGINE, "events": events,
        }, fh, indent=2, ensure_ascii=False)
    print(f"[flow] eventos: {len(events)} -> {EVENTS_PATH}")

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
            print(f"[flow] frame {f + 1}/{FRAMES}")

    print("\n[flow] ====== RESUMEN ======")
    print(f"[flow] motor   : {ENGINE} ({RES_W}x{RES_H}, {SAMPLES} samples)")
    print(f"[flow] frames  : {FRAMES} -> {FRAMES_DIR}")
    print(f"[flow] eventos : {len(events)} -> {EVENTS_PATH}")


if __name__ == "__main__":
    run()
