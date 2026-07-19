import os
import sys

# Agregar la ruta tools al sys.path para importar youtube_uploader
REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

try:
    from youtube_uploader import upload_video_to_youtube
except ImportError as e:
    print("Error: Asegúrate de haber copiado youtube_uploader.py en tools/ y tener las dependencias de Google API instaladas.")
    print(e)
    sys.exit(1)

def main():
    video_path = os.path.join(REPO, "output", "shorts_abc", "shorts_abc.mp4")
    
    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
        
    title = "ABC Flow: 5,000 Particles in a Chaotic 3D Vector Field 🌀✨ #math #physics #shorts"
    description = (
        "The Arnold-Beltrami-Childress (ABC) flow is an exact solution to Euler's inviscid fluid equations! 🌀\n\n"
        "Watch 5,000 particles trace chaotic streamlines through this famous 3D vector field with parameters A=√3, B=√2, C=1. "
        "The ABC flow is one of the simplest examples of a steady-state solution to the Euler equations that exhibits Lagrangian chaos—particles follow wildly unpredictable paths even though the underlying velocity field is perfectly smooth and deterministic.\n\n"
        "Listen to the generative sonification! 🎧 Chaotic bursts in the flow are mapped to pentatonic notes, creating an organic soundscape that mirrors the mathematical turbulence.\n\n"
        "Support the project and discover more mathematics inspired designs at our official store: https://mathrelaxing.store ✨\n\n"
        "#MathRelaxing #ABCFlow #VectorField #FluidDynamics #EulerEquations #PhysicsSimulation #Mathematics #ScienceArt #GenerativeArt"
    )
    tags = [
        "math", "physics", "vector field", "ABC flow", "fluid dynamics",
        "chaotic flow", "euler equations", "python", "blender", "generative art",
        "mathrelaxing", "sonification", "science", "education", "visuals"
    ]
    
    print(f"Subiendo: {video_path}...")
    print("Por favor espera, esto puede tardar un poco dependiendo de tu velocidad de subida.")
    
    def on_progress(p):
        sys.stdout.write(f"\rSubiendo... {p}%")
        sys.stdout.flush()

    try:
        video_id, channel_name = upload_video_to_youtube(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status="public",
            publish_at=None,
            desired_channel="MathRelaxing",
            progress_callback=on_progress
        )
        print(f"\n\n¡Subida completada con éxito en el canal '{channel_name}'!")
        print(f"El video ya es PÚBLICO.")
        print(f"Revisa tu video aquí: https://youtu.be/{video_id}")
    except Exception as e:
        print(f"\n\nError al subir el video a YouTube: {e}")

if __name__ == "__main__":
    main()
