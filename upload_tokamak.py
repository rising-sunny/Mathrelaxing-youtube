import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

try:
    from youtube_uploader import upload_video_to_youtube
except ImportError as e:
    print("Error imports:", e)
    sys.exit(1)

def main():
    video_path = os.path.join(REPO, "output", "shorts_tokamak", "shorts_tokamak.mp4")
    
    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
        
    title = "Tokamak Magnetic Bottle: Confining Plasma in a 3D Torus 🧲✨ #math #physics #shorts"
    description = (
        "How do we bottle a star? 🧲🌟\n\n"
        "Explore the magnetic fields of a Tokamak—the leading design for nuclear fusion reactors! "
        "Watch 4,000 particles flow through a vector field composed of toroidal and poloidal fields, "
        "creating the beautiful twisting helixes that trap superheated plasma inside a torus.\n\n"
        "🎧 Listen to the generative sonification: the speed and topology of the field shape the musical harmony in real-time.\n\n"
        "Support the project and discover more mathematics inspired designs at our official store: https://mathrelaxing.store ✨\n\n"
        "#MathRelaxing #Tokamak #Fusion #PhysicsSimulation #VectorField #MagneticField #ScienceArt #GenerativeArt"
    )
    tags = [
        "math", "physics", "vector field", "tokamak", "fusion", "magnetic field",
        "plasma", "python", "blender", "generative art",
        "mathrelaxing", "sonification", "science", "education", "visuals"
    ]
    
    print(f"Subiendo: {video_path}...")
    
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
