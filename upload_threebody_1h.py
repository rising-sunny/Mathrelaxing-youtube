"""Upload Three-Body Figure-8 1h video + thumbnail to MathRelaxing."""
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
    video_path = os.path.join(REPO, "output", "threebody_1h", "threebody_1h_final.mp4")
    thumbnail_path = os.path.join(REPO, "output", "threebody_1h", "threebody_thumbnail_text.jpg")

    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
    if not os.path.exists(thumbnail_path):
        print(f"Error: No se encontró el thumbnail {thumbnail_path}")
        sys.exit(1)

    title = (
        "1 HOUR Deep Focus ✨ 3-Body Problem Figure-8 — Moore Choreography "
        "(m₁=m₂=m₃) #math #study #physics"
    )
    description = (
        "Dive into deep focus with 1 hour of the three-body problem’s most famous "
        "periodic orbit: the Moore figure-8 choreography.\n\n"
        "Three equal masses chase one another forever along a single ∞-shaped path — "
        "a solution proven by Chenciner & Montgomery. Here, 21,000 glowing particles "
        "trace the three braided bodies in cyan, magenta, and gold, locked to a "
        "mathematically seamless loop with a full 360° camera orbit.\n\n"
        "Math note: with m₁ = m₂ = m₃ and Newtonian gravity (G m² / r²), special "
        "initial conditions yield a stable periodic figure-8. Same laws that make "
        "the general three-body problem chaotic also allow this cosmic ballet.\n\n"
        "🎧 Ambient focus soundscape with generative sonification, drone, and "
        "concentration-friendly tracks. Perfect for studying, coding, reading, "
        "or meditation.\n\n"
        "✨ Discover mathematics-inspired designs and support the channel: "
        "https://mathrelaxing.store\n\n"
        "#MathRelaxing #ThreeBodyProblem #Figure8 #Physics #DeepFocus #StudyMusic "
        "#Ambient #MathArt #GenerativeArt #Python #Gravity #MooreChoreography #Meditation"
    )
    tags = [
        "math", "three body problem", "figure 8", "physics", "deep focus",
        "study music", "1 hour", "ambient", "meditation", "generative art",
        "mathrelaxing", "python", "gravity", "moore choreography", "focus music",
        "n-body", "orbital mechanics",
    ]

    print(f"Subiendo: {video_path}...")
    print(f"Miniatura: {thumbnail_path}")

    def on_progress(p):
        sys.stdout.write(f"\rSubiendo... {p}%")
        sys.stdout.flush()

    video_id, channel_name = upload_video_to_youtube(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        privacy_status="public",
        desired_channel="MathRelaxing",
        progress_callback=on_progress,
        thumbnail_path=thumbnail_path,
    )
    print(f"\n\n¡Subida completada en '{channel_name}'!")
    print(f"PÚBLICO: https://youtu.be/{video_id}")
    return video_id


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n\nError al subir el video a YouTube: {e}")
        sys.exit(1)
