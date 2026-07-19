import bpy
import numpy as np
import os
import sys
import json
import argparse
import math

def setup_scene(res_w=576, res_h=1024, engine="eevee"):
    # Clear existing data
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Render settings
    scene = bpy.context.scene
    scene.render.resolution_x = res_w
    scene.render.resolution_y = res_h
    scene.render.fps = 60
    
    # Configure Eevee
    if engine == "eevee":
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    else:
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'GPU'
        scene.cycles.samples = 128

    # World / Environment
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get('Background')
    if bg_node:
        bg_node.inputs[0].default_value = (0.01, 0.01, 0.02, 1) # Very dark blue
        bg_node.inputs[1].default_value = 1.0
        
    # Camera setup (Top-down angled)
    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (0, -2.5, 3.5)
    cam.rotation_euler = (math.radians(35), 0, 0)
    cam.data.lens = 35

    # Dramatic Lighting
    light_data = bpy.data.lights.new(name="Spot", type='SPOT')
    light = bpy.data.objects.new(name="Spot", object_data=light_data)
    bpy.context.collection.objects.link(light)
    light.location = (2, -2, 4)
    light.rotation_euler = (math.radians(30), math.radians(20), 0)
    light_data.energy = 500
    light_data.color = (0.8, 0.9, 1.0) # Cool blue rim light
    light_data.spot_size = math.radians(60)
    light_data.spot_blend = 0.5
    
    light_data2 = bpy.data.lights.new(name="Point", type='POINT')
    light2 = bpy.data.objects.new(name="Point", object_data=light_data2)
    bpy.context.collection.objects.link(light2)
    light2.location = (-1.5, 1.5, 0.5)
    light_data2.energy = 200
    light_data2.color = (1.0, 0.6, 0.1) # Warm orange low light

    # The Plate
    bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, 0))
    plate = bpy.context.active_object
    plate.name = "ChladniPlate"
    plate_mat = bpy.data.materials.new(name="PlateMat")
    plate_mat.use_nodes = True
    bsdf = plate_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.02, 0.02, 0.02, 1)
        bsdf.inputs['Metallic'].default_value = 0.8
        bsdf.inputs['Roughness'].default_value = 0.2
    plate.data.materials.append(plate_mat)

def create_particles_mesh(N):
    mesh = bpy.data.meshes.new("SandMesh")
    obj = bpy.data.objects.new("Sand", mesh)
    bpy.context.collection.objects.link(obj)
    
    # Initialize vertices (no faces)
    coords = np.zeros(N * 3, dtype=np.float32)
    mesh.vertices.add(N)
    mesh.vertices.foreach_set("co", coords)
    
    # Create Material for Sand
    mat = bpy.data.materials.new(name="SandMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        geo = nodes.new(type="ShaderNodeNewGeometry")
        
        vec_math = nodes.new(type="ShaderNodeVectorMath")
        vec_math.operation = 'LENGTH'
        links.new(geo.outputs['Position'], vec_math.inputs[0])
        
        map_range = nodes.new(type="ShaderNodeMapRange")
        map_range.inputs[1].default_value = 0.0
        map_range.inputs[2].default_value = 1.0
        
        links.new(vec_math.outputs['Value'], map_range.inputs['Value'])
        
        color_ramp = nodes.new(type="ShaderNodeValToRGB")
        color_ramp.color_ramp.elements[0].position = 0.0
        color_ramp.color_ramp.elements[0].color = (1.0, 0.1, 0.3, 1.0)
        color_ramp.color_ramp.elements[1].position = 0.6
        color_ramp.color_ramp.elements[1].color = (0.2, 0.8, 1.0, 1.0)
        elem2 = color_ramp.color_ramp.elements.new(1.0)
        elem2.color = (0.8, 0.2, 1.0, 1.0)
        
        links.new(map_range.outputs['Result'], color_ramp.inputs['Fac'])
        
        bsdf.inputs['Metallic'].default_value = 0.9
        bsdf.inputs['Roughness'].default_value = 0.1
        bsdf.inputs['Emission Strength'].default_value = 3.0
        
        links.new(color_ramp.outputs['Color'], bsdf.inputs['Base Color'])
        links.new(color_ramp.outputs['Color'], bsdf.inputs['Emission Color'])

    # Geometry Nodes setup
    mod = obj.modifiers.new(name="GeoNodes", type='NODES')
    node_tree = bpy.data.node_groups.new(name="Instancer", type='GeometryNodeTree')
    mod.node_group = node_tree
    
    # Build tree
    node_tree.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    node_tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    
    node_in = node_tree.nodes.new('NodeGroupInput')
    node_out = node_tree.nodes.new('NodeGroupOutput')
    
    iop = node_tree.nodes.new('GeometryNodeInstanceOnPoints')
    sphere = node_tree.nodes.new('GeometryNodeMeshUVSphere')
    sphere.inputs['Radius'].default_value = 0.005 # Tiny grains
    sphere.inputs['Segments'].default_value = 8
    sphere.inputs['Rings'].default_value = 4
    
    set_mat = node_tree.nodes.new('GeometryNodeSetMaterial')
    set_mat.inputs['Material'].default_value = mat
    
    node_tree.links.new(node_in.outputs[0], iop.inputs['Points'])
    node_tree.links.new(sphere.outputs[0], set_mat.inputs['Geometry'])
    node_tree.links.new(set_mat.outputs[0], iop.inputs['Instance'])
    node_tree.links.new(iop.outputs[0], node_out.inputs[0])
    
    return obj, mesh

def load_audio_events():
    events_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "audio_driven_events.json")
    try:
        with open(events_path, "r") as f:
            data = json.load(f)
            return data["events"], data["fps"], data["duration_s"]
    except Exception as e:
        print(f"Error loading audio events: {e}")
        return [], 60, 10.0

def run_simulation(N, frames, fps=60):
    rng = np.random.default_rng(42)
    P = rng.uniform(-1.0, 1.0, size=(N, 3)).astype(np.float32)
    P[:, 2] = rng.uniform(0.0, 0.5, size=N)
    V = np.zeros((N, 3), dtype=np.float32)
    
    obj, mesh = create_particles_mesh(N)
    
    substeps = 4
    dt = (1.0 / fps) / substeps
    
    # Load audio events
    audio_events, audio_fps, audio_dur = load_audio_events()
    if frames <= 0 and len(audio_events) > 0:
        frames = len(audio_events)
    elif frames <= 0:
        frames = 600 # fallback
        
    for f in range(frames):
        if f < len(audio_events):
            ev = audio_events[f]
            m = ev["m"]
            n = ev["n"]
            audio_speed = ev["speed"]
        else:
            m, n, audio_speed = 1.0, 1.0, 0.1
            
        # We don't save events back since they already come from audio
        pass
        
        for _ in range(substeps):
            u = (P[:, 0] + 1.0) * 0.5
            v = (P[:, 1] + 1.0) * 0.5
            
            # Chladni amplitude
            W = np.sin(n * np.pi * u) * np.sin(m * np.pi * v) + \
                np.sin(m * np.pi * u) * np.sin(n * np.pi * v)
            
            # Only affect particles close to the plate
            on_plate = P[:, 2] <= 0.005
            
            # Gravity
            V[:, 2] -= 9.81 * dt
            
            # Bounce and kick
            # Bounce and kick
            kick = np.abs(W) * 150.0 * dt
            # Scale kick exponentially so nodes really collect particles
            kick = kick ** 1.5 
            
            # Apply audio volume (speed) to kick
            kick = kick * (1.0 + audio_speed * 3.0)
            
            random_kick = kick * rng.uniform(0.5, 1.5, size=N)
            
            # Restitution (loss of energy)
            V[on_plate, 2] = np.abs(V[on_plate, 2]) * 0.6 + random_kick[on_plate]
            
            # Scatter (push away from antinodes)
            scatter = rng.normal(0, 1.0, size=(N, 2)) * random_kick[:, np.newaxis] * 0.8
            V[on_plate, :2] += scatter[on_plate]
            
            # Global jitter to prevent complete sticking
            jitter = rng.normal(0, 1.0, size=(N, 2)) * 0.5 * dt
            V[on_plate, :2] += jitter[on_plate]
            
            # Edge repulsion to prevent particles accumulating exactly on the boundary
            margin = 0.95
            edge_x = np.where(P[:, 0] > margin, margin - P[:, 0], np.where(P[:, 0] < -margin, -margin - P[:, 0], 0))
            edge_y = np.where(P[:, 1] > margin, margin - P[:, 1], np.where(P[:, 1] < -margin, -margin - P[:, 1], 0))
            V[:, 0] += edge_x * 100.0 * dt
            V[:, 1] += edge_y * 100.0 * dt
            
            # Friction on plate
            V[on_plate, :2] *= 0.96
            
            # Air drag
            V[:, :2] *= 0.99
            
            P += V * dt
            
            # Constraints
            P[:, 0] = np.clip(P[:, 0], -0.98, 0.98)
            P[:, 1] = np.clip(P[:, 1], -0.98, 0.98)
            P[:, 2] = np.maximum(P[:, 2], 0.0)
            
        # Update mesh
        mesh.vertices.foreach_set("co", P.flatten())
        
        # Render frame
        bpy.context.scene.frame_set(f)
        if f % 100 == 0:
            print(f"Rendered frame {f}/{frames}")
        out_path = os.path.join(base_path, f"{f:04d}.png")
        if not os.path.exists(out_path):
            bpy.context.scene.render.filepath = out_path
            bpy.ops.render.render(write_still=True)
            bpy.context.scene.render.filepath = base_path
            
    return audio_events

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default="eevee", choices=["eevee", "cycles"])
    parser.add_argument("--res", type=int, default=1024)
    parser.add_argument("--format", type=str, default="9:16")
    parser.add_argument("--frames", type=int, default=900)
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--name", type=str, default="shorts_chladni")
    
    # Filter args after "--"
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
    bpy.context.scene.eevee.taa_render_samples = a.samples
    
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(repo, "output", a.name)
    frames_dir = os.path.join(outdir, "frames")
    os.makedirs(frames_dir, exist_ok=True)
    
    global base_path
    base_path = frames_dir
    bpy.context.scene.render.filepath = frames_dir + "/"
    
    N_particles = 50000
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
