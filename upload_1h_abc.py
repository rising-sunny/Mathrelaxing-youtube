import os
import sys

# Agregar la ruta tools al sys.path para importar youtube_uploader
REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

try:
    from paths import thumbnail_path as thumb_file
    from youtube_uploader import upload_video_to_youtube
except ImportError as e:
    print("Error: Asegúrate de haber copiado youtube_uploader.py en tools/ y tener las dependencias instaladas.")
    print(e)
    sys.exit(1)

def main():
    video_path = os.path.join(REPO, "output", "abc_loop_preview", "abc_flow_1h_final.mp4")
    thumbnail_path = thumb_file("abc_thumbnail_v5_compressed.jpg", create=False)
    
    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
        
    title = "1 HOUR Deep Focus 🌀 Chaotic Math Vector Field for Study & Relaxation (ABC Flow)"
    description = (
        "Immerse yourself in 1 hour of deep focus and relaxation with this mesmerizing mathematical visualization. 🧠✨\n\n"
        "This video features an infinite loop of 5,000 particles tracing chaotic streamlines through the Arnold-Beltrami-Childress (ABC) flow—an exact solution to Euler's inviscid fluid equations! With parameters A=√3, B=√2, C=1, particles follow wildly unpredictable paths even though the velocity field is perfectly smooth and deterministic.\n\n"
        "🎧 The generative sonification transforms the mathematical turbulence into an organic soundscape, accompanied by an ambient drone and a continuous mix of focus-enhancing music from Epidemic Sound. Perfect for studying, coding, reading, or deep relaxation.\n\n"
        "Support the project and discover more mathematics inspired designs at our official store: https://mathrelaxing.store ✨\n\n"
        "#MathRelaxing #StudyMusic #DeepFocus #ABCFlow #VectorField #FluidDynamics #ChaosTheory #AmbientMusic #GenerativeArt #Relaxation"
    )
    tags = [
        "math", "study music", "deep focus", "1 hour relaxation", "vector field", 
        "ABC flow", "fluid dynamics", "chaotic flow", "ambient music", "generative art",
        "mathrelaxing", "sonification", "science", "focus", "visuals"
    ]
    
    print(f"Subiendo: {video_path}...")
    print(f"Miniatura: {thumbnail_path}")
    print("Por favor espera, esto puede tardar bastante (el video pesa ~10GB).")
    
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
            progress_callback=on_progress,
            thumbnail_path=thumbnail_path
        )
        print(f"\n\n¡Subida completada con éxito en el canal '{channel_name}'!")
        print(f"El video ya es PÚBLICO.")
        print(f"Revisa tu video aquí: https://youtu.be/{video_id}")
    except Exception as e:
        print(f"\n\nError al subir el video a YouTube: {e}")

if __name__ == "__main__":
    main()
