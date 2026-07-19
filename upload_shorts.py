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
    video_path = os.path.join(REPO, "output", "shorts_curl", "shorts_curl.mp4")
    
    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
        
    title = "Curl Noise Flow Field: 2,000 Particles of Pure Math 🌊✨ #math #physics #shorts"
    description = (
        "What does an incompressible fluid look like? 🌊\n\n"
        "Watch 2,000 particles flow through a 3D Curl Noise vector field. By taking the mathematical curl of a Perlin noise field, the resulting flow has exactly zero divergence—meaning the particles behave like a liquid, flowing organically without ever clustering together.\n\n"
        "Listen to the generative sonification! 🎧 The physics engine maps the velocity of the flow to notes on a pentatonic scale, creating a relaxing generative arpeggio while soft water-drop strikes mark the chaotic surges.\n\n"
        "Support the project and discover more mathematics inspired designs at our official store: https://mathrelaxing.store ✨\n\n"
        "#MathRelaxing #VectorField #CurlNoise #FluidDynamics #PhysicsSimulation #Mathematics #ScienceArt #STEM #GenerativeArt"
    )
    tags = [
        "math", "physics", "vector field", "curl noise", "fluid dynamics",
        "python", "blender", "generative art", "mathrelaxing", "sonification", 
        "science", "education", "visuals"
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
