import os
import subprocess
import sys

def main():
    repo = "C:/dev/MathRelaxing-videos-music"
    frames_dir = os.path.join(repo, "output/shorts_reaction/frames")
    
    # Step 1: Generate frames (no Blender needed now)
    count = 0
    if os.path.exists(frames_dir):
        count = len([f for f in os.listdir(frames_dir) if f.endswith(".png")])
    
    if count < 900:
        print(f"Fotogramas existentes: {count}. Generando frames...")
        subprocess.run([
            sys.executable,
            os.path.join(repo, "scenes", "reaction_diffusion.py"),
            "--frames", "900", "--grid", "256",
            "--width", "576", "--height", "1024"
        ], check=True, cwd=repo)
    else:
        print("Todos los fotogramas ya existen.")
    
    # Step 2: Assembly (audio, overlay, mux)
    print("Iniciando ensamblaje final (audio, overlay, mux)...")
    subprocess.run([
        sys.executable, "render/build_clip.py", 
        "--name", "shorts_reaction", 
        "--scene", "scenes/reaction_diffusion.py", 
        "--skip-render",
        "--engine", "eevee", "--frames", "900", 
        "--res", "1024", "--format", "9:16", 
        "--math-overlay", "--waveform", 
        "--attractor", "reaction_diffusion", "--fps", "60"
    ], check=True, cwd=repo)
    print("TODO LISTO!")

if __name__ == "__main__":
    main()
