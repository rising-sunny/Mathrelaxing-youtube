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
    video_path = os.path.join(REPO, "output", "shorts_lorenz", "shorts_lorenz.mp4")
    
    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
        
    title = "The Butterfly Effect: 15,000 Particles in the Lorenz Attractor (1963) 🦋✨ #math #shorts"
    description = (
        "In 1963, meteorologist Edward Lorenz discovered Chaos Theory by accident. "
        "He found that a tiny rounding error in his weather simulation completely changed the outcome—"
        "proving that a butterfly flapping its wings in Brazil could set off a tornado in Texas.\n\n"
        "Watch 15,000 particles navigate the strange attractor that birthed chaos theory, rendered natively in Python! "
        "The particles split into two distinct 'wings' (Cyan and Magenta), generating beautiful generative harmonies every time the swarm crosses the center plane.\n\n"
        "✨ Support the project and discover mathematics inspired designs at our official store: https://mathrelaxing.store\n\n"
        "#MathRelaxing #LorenzAttractor #ButterflyEffect #ChaosTheory #PhysicsSimulation #GenerativeArt #Python #Science"
    )
    tags = [
        "math", "physics", "chaos theory", "lorenz attractor", "butterfly effect", 
        "python", "numpy", "fractal", "generative art", "mathrelaxing", "sonification", 
        "science", "education", "visuals"
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
