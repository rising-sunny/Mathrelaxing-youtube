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
    video_path = os.path.join(REPO, "output", "aizawa_1h", "aizawa_1h_final.mp4")
    
    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
        
    title = "Aizawa Attractor - 1 HOUR DEEP FOCUS - The Cosmic Sphere 🌌✨ #math #study #meditation"
    description = (
        "Dive into deep focus with 1 hour of continuous, seamless Aizawa Attractor simulation. "
        "Watch 30,000 glowing particles trace the complex chaotic orbits of 'The Cosmic Sphere', accompanied by Betawaves for Concentration. "
        "Perfect for studying, meditating, or coding. \n\n"
        "✨ Discover mathematics-inspired designs and support the channel at our official store: https://mathrelaxing.store\n\n"
        "#MathRelaxing #AizawaAttractor #ChaosTheory #DeepFocus #StudyMusic #Ambient #MathArt #Python #GenerativeArt"
    )
    tags = [
        "math", "physics", "aizawa attractor", "chaos theory", "study music", "deep focus", "ambient",
        "betawaves", "meditation", "generative art", "mathrelaxing", "python", "numpy"
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
