import os
import sys

# Agregar la ruta tools al sys.path para importar youtube_uploader
REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from youtube_uploader import upload_video_to_youtube

def main():
    video_path = os.path.join(REPO, "output", "shorts_chladni", "shorts_chladni.mp4")
    
    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
        
    title = "Chladni Plates: Seeing Sound (50,000 Particles Physics Simulation) #math #physics #satisfying"
    description = (
        "Witness the beautiful chaos of cymatics! ✨\n\n"
        "A massive simulation of 50,000 particles responding to the Chladni wave equation. As the audio frequency shifts, the particles are violently catapulted away from the antinodes to form perfectly stable geometric nodes.\n\n"
        "Support the project and discover more mathematics inspired designs at our official store: https://mathrelaxing.store ✨\n\n"
        "#MathRelaxing #Cymatics #ChladniPlates #PhysicsSimulation #Mathematics #ScienceArt #STEM #GenerativeArt #Blender3D"
    )
    tags = [
        "cymatics", "chladni plates", "physics simulation", "blender 3d", "math", 
        "geometry", "satisfying", "sound waves", "science", "physics", "cimática"
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
