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
    video_path = os.path.join(REPO, "output", "thomas_1h", "thomas_1h_final.mp4")
    
    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
        
    title = "1 Hour of Deep Focus: 25,000 Particles in the Thomas Cyclically Symmetric Attractor 🌌✨"
    description = (
        "Dive into deep concentration and meditation with 1 hour of the mesmerizing Thomas Cyclically Symmetric Attractor. "
        "25,000 particles flow in a perfectly seamless loop, mathematically calculated to never break your immersion.\n\n"
        "Rendered entirely in Python with a bespoke mathematical glow engine. The generative harmonies adapt as the chaotic system fluctuates, ducking seamlessly under a curated mix of deep focus ambient tracks.\n\n"
        "✨ Discover mathematics-inspired designs and support the channel at our official store: https://mathrelaxing.store\n\n"
        "#MathRelaxing #ThomasAttractor #DeepFocus #ChaosTheory #AmbientMusic #StudyMusic #GenerativeArt #Python #Fractal #MathArt"
    )
    tags = [
        "math", "physics", "chaos theory", "thomas attractor", "deep focus", "ambient music", 
        "study music", "sleep music", "meditation", "generative art", "mathrelaxing", "python", 
        "fractal", "science", "education", "visuals"
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
