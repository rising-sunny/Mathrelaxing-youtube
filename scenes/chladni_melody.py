import bpy
import numpy as np
import os
import sys
import argparse
import json

# ==============================================================================
# Escena y Renderizado
# ==============================================================================
def setup_scene(res_w=1024, res_h=1024, engine="eevee"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT' if engine == 'eevee' else 'CYCLES'
    scene.render.resolution_x = res_w
    scene.render.resolution_y = res_h
    scene.render.fps = 60
    
    # Eevee Next settings
    if engine == "eevee" and hasattr(scene, "eevee"):
        scene.eevee.use_gtao = True
        
    if "World" in bpy.data.worlds:
        world = bpy.data.worlds["World"]
    else:
        world = bpy.data.worlds.new("World")
        scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.01, 0.01, 0.01, 1)

    # Lighting
    light_data = bpy.data.lights.new(name="Spot", type='SPOT')
    light_data.energy = 2000
    light_data.spot_size = 1.0
    light_data.spot_blend = 0.5
    light_obj = bpy.data.objects.new(name="Spot", object_data=light_data)
    bpy.context.collection.objects.link(light_obj)
    light_obj.location = (0, -2.5, 3.0)
    light_obj.rotation_euler = (0.7, 0, 0)
    
    # Camera
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 35
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = (0, -2.0, 2.0)
    cam_obj.rotation_euler = (np.deg2rad(45), 0, 0)
    scene.camera = cam_obj
    
    # Plate
    bpy.ops.mesh.primitive_plane_add(size=2.0)
    plate = bpy.context.active_object
    mat_plate = bpy.data.materials.new("PlateMat")
    mat_plate.use_nodes = True
    bsdf = mat_plate.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.05, 0.05, 0.05, 1)
        bsdf.inputs['Metallic'].default_value = 1.0
        bsdf.inputs['Roughness'].default_value = 0.3
    plate.data.materials.append(mat_plate)

# ==============================================================================
# Arena (Nodos de Geometría)
# ==============================================================================
def create_particles_mesh(N=300000):
    mesh = bpy.data.meshes.new("SandMesh")
    obj = bpy.data.objects.new("Sand", mesh)
    bpy.context.collection.objects.link(obj)
    
    # Initialize vertices
    coords = np.zeros(N * 3, dtype=np.float32)
    mesh.vertices.add(N)
    mesh.vertices.foreach_set("co", coords)
    
    # Realistic Sand Material
    mat = bpy.data.materials.new(name="SandMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.9, 0.8, 0.6, 1.0) # Light sand color
        bsdf.inputs['Metallic'].default_value = 0.1
        bsdf.inputs['Roughness'].default_value = 0.8

    # Geometry Nodes setup
    mod = obj.modifiers.new(name="GeoNodes", type='NODES')
    node_tree = bpy.data.node_groups.new(name="Instancer", type='GeometryNodeTree')
    mod.node_group = node_tree
    
    node_tree.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    node_tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    
    node_in = node_tree.nodes.new('NodeGroupInput')
    node_out = node_tree.nodes.new('NodeGroupOutput')
    
    iop = node_tree.nodes.new('GeometryNodeInstanceOnPoints')
    sphere = node_tree.nodes.new('GeometryNodeMeshUVSphere')
    sphere.inputs['Radius'].default_value = 0.0015 # Tiny sand grains
    sphere.inputs['Segments'].default_value = 6
    sphere.inputs['Rings'].default_value = 3
    
    set_mat = node_tree.nodes.new('GeometryNodeSetMaterial')
    set_mat.inputs['Material'].default_value = mat
    
    node_tree.links.new(node_in.outputs[0], iop.inputs['Points'])
    node_tree.links.new(sphere.outputs[0], set_mat.inputs['Geometry'])
    node_tree.links.new(set_mat.outputs[0], iop.inputs['Instance'])
    node_tree.links.new(iop.outputs[0], node_out.inputs[0])
    
    return obj, mesh

# ==============================================================================
# Lógica de Vibración Chladni (Melodía generativa)
# ==============================================================================
def run_simulation(N=300000, frames=900):
    obj, mesh = create_particles_mesh(N)
    
    rng = np.random.default_rng(42)
    P = rng.uniform(-1.0, 1.0, size=(N, 3)).astype(np.float32)
    P[:, 2] = rng.uniform(0.0, 0.2, size=N)
    V = np.zeros((N, 3), dtype=np.float32)
    
    L = 1.0
    substeps = 4
    fps = 60
    dt = (1.0 / fps) / substeps
    
    melody = [
        (1, 2), (2, 2), (1, 3), (2, 3), (1, 4), 
        (2, 4), (3, 3), (2, 4), (1, 4), (2, 3), 
        (1, 3), (2, 2), (1, 2), (3, 3), (2, 4)
    ]
    
    events_export = []
    
    for f in range(frames):
        note_idx = min(f // 60, len(melody) - 1)
        m, n = melody[note_idx]
        
        frame_in_note = f % 60
        if frame_in_note < 10:
            speed = 1.0 - (frame_in_note / 10.0)
        else:
            speed = 0.0
            
        events_export.append({"frame": f, "m": m, "n": n, "speed": speed})
        
        for _ in range(substeps):
            u = (P[:, 0] + 1.0) * 0.5
            v = (P[:, 1] + 1.0) * 0.5
            
            # W = np.sin(n * np.pi * u) * np.sin(m * np.pi * v) + np.sin(m * np.pi * u) * np.sin(n * np.pi * v)
            # Using the cosine formula for different aesthetics
            W = np.cos(n * np.pi * P[:, 0]) * np.cos(m * np.pi * P[:, 1]) - np.cos(m * np.pi * P[:, 0]) * np.cos(n * np.pi * P[:, 1])
            
            on_plate = P[:, 2] <= 0.005
            V[:, 2] -= 9.81 * dt
            
            # Kick depends on W and speed
            kick = np.abs(W) * 150.0 * dt
            kick = kick ** 1.5 
            # Make the kick highly responsive to the melodic speed pulse
            kick = kick * (1.0 + speed * 5.0)
            
            random_kick = kick * rng.uniform(0.5, 1.5, size=N)
            
            V[on_plate, 2] = np.abs(V[on_plate, 2]) * 0.6 + random_kick[on_plate]
            
            scatter = rng.normal(0, 1.0, size=(N, 2)) * random_kick[:, np.newaxis] * 0.8
            V[on_plate, :2] += scatter[on_plate]
            
            jitter = rng.normal(0, 1.0, size=(N, 2)) * 0.5 * dt
            V[on_plate, :2] += jitter[on_plate]
            
            margin = 0.95
            edge_x = np.where(P[:, 0] > margin, margin - P[:, 0], np.where(P[:, 0] < -margin, -margin - P[:, 0], 0))
            edge_y = np.where(P[:, 1] > margin, margin - P[:, 1], np.where(P[:, 1] < -margin, -margin - P[:, 1], 0))
            V[:, 0] += edge_x * 100.0 * dt
            V[:, 1] += edge_y * 100.0 * dt
            
            V[on_plate, :2] *= 0.94
            V[:, :2] *= 0.99
            
            P += V * dt
            
            P[:, 0] = np.clip(P[:, 0], -0.98, 0.98)
            P[:, 1] = np.clip(P[:, 1], -0.98, 0.98)
            P[:, 2] = np.maximum(P[:, 2], 0.0)
            
        mesh.vertices.foreach_set("co", P.flatten())
        
        bpy.context.scene.frame_set(f)
        
        global base_path
        out_path = os.path.join(base_path, f"{f:04d}.png")
        if not os.path.exists(out_path):
            bpy.context.scene.render.filepath = out_path
            bpy.ops.render.render(write_still=True)
            
        if f % 30 == 0:
            print(f"Frame {f}/{frames} - Note: m={m}, n={n}")
            
    return events_export

# ==============================================================================
# Main
# ==============================================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default="eevee", choices=["eevee", "cycles"])
    parser.add_argument("--res", type=int, default=1024)
    parser.add_argument("--format", type=str, default="9:16")
    parser.add_argument("--frames", type=int, default=900)
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--name", type=str, default="shorts_melody")
    
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    
    a, _ = parser.parse_known_args(argv)
    
    res_w = a.res if a.format == "1:1" else int(a.res * 9 / 16)
    res_h = a.res
    
    setup_scene(res_w=res_w, res_h=res_h, engine=a.engine)
    bpy.context.scene.cycles.samples = a.samples
    if hasattr(bpy.context.scene, "eevee"):
        bpy.context.scene.eevee.taa_render_samples = a.samples
    
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(repo, "output", a.name)
    frames_dir = os.path.join(outdir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    
    global base_path
    base_path = frames_dir
    bpy.context.scene.render.filepath = frames_dir + "/"
    
    N_particles = 300000
    events = run_simulation(N=N_particles, frames=a.frames)
    
    meta = {
        "duration_s": a.frames / 60.0,
        "fps": 60,
        "events": events
    }
    
    events_path = os.path.join(repo, "data", f"{a.name}_events.json")
    os.makedirs(os.path.dirname(events_path), exist_ok=True)
    with open(events_path, "w") as f:
        json.dump(meta, f)
        
if __name__ == "__main__":
    main()
