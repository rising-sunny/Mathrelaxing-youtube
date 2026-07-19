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
    video_path = os.path.join(REPO, "output", "circular_cymatics", "circular_cymatics_final.mp4")
    
    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
        
    title = "Circular Cymatics: 300,000 Grains of Sand Forming Bessel Functions 🌸✨ #math #physics #shorts"
    description = (
        "Watch 300,000 glowing grains of sand form perfect acoustic flowers and stars on a circular cymatic plate. "
        "Unlike square plates, circular plates vibrate according to Bessel functions, creating mesmerizing radial and concentric nodal patterns. "
        "Each frequency locks the sand into a new mathematical mandala!\n\n"
        "✨ Discover mathematics-inspired designs and support the channel at our official store: https://mathrelaxing.store\n\n"
        "#MathRelaxing #Cymatics #BesselFunctions #Physics #GenerativeArt #Python #MathArt"
    )
    tags = [
        "math", "physics", "cymatics", "chladni plate", "bessel functions", "generative art", 
        "mathrelaxing", "python", "numpy", "mandala", "science", "education", "visuals"
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
