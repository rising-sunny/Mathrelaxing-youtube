import os
import subprocess
import time
import sys

def main():
    repo = "C:/dev/MathRelaxing-videos-music"
    frames_dir = os.path.join(repo, "output/shorts_chladni/frames")
    
    blender_exe = os.path.join(repo, "tools/blender/blender-4.4.3-windows-x64/blender.exe")
    scene = os.path.join(repo, "scenes/chladni_plate.py")
    
    while True:
        count = 0
        if os.path.exists(frames_dir):
            count = len([f for f in os.listdir(frames_dir) if f.endswith(".png")])
        print(f"Fotogramas renderizados: {count}/900")
        if count >= 900:
            print("Renderizado completo. Pasando a ensamblaje...")
            break
            
        print("Lanzando Blender...")
        try:
            subprocess.run([
                blender_exe, "--background", "--python", scene, "--",
                "--engine", "eevee", "--frames", "900", "--res", "1024",
                "--samples", "32", "--name", "shorts_chladni", "--format", "9:16"
            ], check=True)
            break
        except subprocess.CalledProcessError as e:
            print(f"Blender crash (code {e.returncode}). Reiniciando en 3s...")
            time.sleep(3)
            
    print("Iniciando ensamblaje final (audio, overlay, mux)...")
    subprocess.run([
        sys.executable, "render/build_clip.py", 
        "--name", "shorts_chladni", 
        "--scene", "scenes/chladni_plate.py", 
        "--skip-render",
        "--engine", "eevee", "--frames", "900", 
        "--res", "1024", "--format", "9:16", 
        "--math-overlay", "--waveform", 
        "--attractor", "chladni", "--fps", "60"
    ], check=True, cwd=repo)
    print("TODO LISTO!")

if __name__ == "__main__":
    main()
