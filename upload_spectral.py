import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

try:
    from youtube_uploader import upload_video_to_youtube
except ImportError as e:
    print("Error: falta tools/youtube_uploader.py o dependencias de Google API.")
    print(e)
    sys.exit(1)


def main():
    video_path = os.path.join(REPO, "output", "shorts_spectral", "shorts_spectral.mp4")
    if not os.path.exists(video_path):
        print(f"Error: no se encontró {video_path}")
        sys.exit(1)

    title = (
        "Spectral Cymatics: Standing Waves Driven by Sound 🌊✨ "
        "#math #physics #shorts"
    )
    description = (
        "What does music look like as a standing wave field?\n\n"
        "This short renders spectral cymatics in pure Python (no Blender): "
        "polar interference modes whose amplitudes Aᵢ follow the energy in six "
        "frequency bands of the track. Brightness and complexity track RMS, "
        "spectral centroid, and onsets in real time.\n\n"
        "W(r,θ,t) = Σ Aᵢ(t) cos(kᵢ r − ωᵢ t) cos(mᵢ θ + φᵢ)\n"
        "with Aᵢ ∝ Eᵢ(ω) and angular harmonics mᵢ ∈ {2,3,4,5,7,9}.\n\n"
        "Music: \"How Did We Get Here\" — Hanna Lindgren (Epidemic Sound)\n\n"
        "Support the project: https://mathrelaxing.store ✨\n\n"
        "#MathRelaxing #Cymatics #SpectralAnalysis #Physics #Mathematics "
        "#ScienceArt #STEM #GenerativeArt #Shorts #Ambient"
    )
    tags = [
        "math", "physics", "cymatics", "spectral", "standing waves",
        "python", "generative art", "mathrelaxing", "science",
        "education", "visuals", "shorts", "ambient", "sound visualization",
    ]

    print(f"Subiendo: {video_path}...")
    print("Canal destino: MathRelaxing (público)")

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
            progress_callback=on_progress,
        )
        print(f"\n\n¡Subida completada en '{channel_name}'!")
        print(f"Público: https://youtu.be/{video_id}")
    except Exception as e:
        print(f"\n\nError al subir: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
