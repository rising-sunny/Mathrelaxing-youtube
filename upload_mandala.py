import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

try:
    from youtube_uploader import upload_video_to_youtube
except ImportError as e:
    print("Error: Asegúrate de haber copiado youtube_uploader.py en tools/ y tener las dependencias de Google API instaladas.")
    print(e)
    sys.exit(1)

def main():
    video_path = os.path.join(REPO, "output", "shorts_mandala", "shorts_mandala.mp4")

    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)

    title = "Cymatic Mandala: 300,000 Grains of Sand Painting a Living Spiral 🌈🌀 #math #physics #shorts"
    description = (
        "What does sound look like when it gets more complex? 🌀✨\n\n"
        "Watch 300,000 grains of sand snap into a living mandala on a circular Chladni plate. As the acoustic "
        "wave modes (m, n) climb step by step, the pattern escalates from a single simple spiral all the way to "
        "an intricate high-order flower of nodes — and every grain is colored by its own angle on the plate, "
        "so the mandala paints itself in a full spectrum as it forms.\n\n"
        "🎧 The soundtrack is generated directly from the physics: every new mode triggers a deep, haunting bell "
        "struck with echo, a continuous granular texture that surges like real sand rushing into place, and a "
        "slow-building melodic bassline in C harmonic minor that climbs toward a climax right as the mandala "
        "reaches its most intricate form.\n\n"
        "Support the project and discover more mathematics inspired designs at our official store: https://mathrelaxing.store ✨\n\n"
        "#MathRelaxing #Chladni #Cymatics #Mandala #Acoustics #PhysicsSimulation #Mathematics #ScienceArt #STEM #GenerativeArt"
    )
    tags = [
        "math", "physics", "chladni", "cymatics", "mandala",
        "acoustics", "python", "generative art", "mathrelaxing",
        "sonification", "science", "education", "visuals", "satisfying"
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
