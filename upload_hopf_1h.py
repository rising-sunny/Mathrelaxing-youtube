"""Upload Hopf Fibration 1h video + thumbnail to MathRelaxing."""
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
    video_path = os.path.join(REPO, "output", "hopf_1h", "hopf_1h_final.mp4")
    thumbnail_path = os.path.join(REPO, "output", "hopf_1h", "hopf_thumbnail_text.jpg")

    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
    if not os.path.exists(thumbnail_path):
        print(f"Error: No se encontró el thumbnail {thumbnail_path}")
        sys.exit(1)

    title = (
        "1 HOUR Deep Focus ✨ Hopf Fibration — Linked Circles in S³ "
        "(η : S³ → S²) #math #study #meditation"
    )
    description = (
        "Dive into deep focus with 1 hour of the Hopf fibration — one of the most "
        "beautiful maps in topology: η : S³ → S².\n\n"
        "Watch 28,000 glowing particles ride the circular S¹ fibers of S³, "
        "stereographically projected into 3D as perfectly linked rainbow circles. "
        "The motion is mathematically seamless: a pure 2π-periodic loop with a "
        "full 360° camera orbit.\n\n"
        "🎧 Ambient focus soundscape with generative sonification, drone, and "
        "concentration-friendly tracks. Perfect for studying, coding, reading, "
        "or meditation.\n\n"
        "Math note: the Hopf fibration maps every point of the 3-sphere to a circle "
        "fiber over the 2-sphere. After stereographic projection, those fibers "
        "appear as nested, linked circles in R³ — the structure you see here.\n\n"
        "✨ Discover mathematics-inspired designs and support the channel: "
        "https://mathrelaxing.store\n\n"
        "#MathRelaxing #HopfFibration #Topology #DeepFocus #StudyMusic #Ambient "
        "#MathArt #GenerativeArt #Python #Geometry #Meditation #S3"
    )
    tags = [
        "math", "hopf fibration", "topology", "deep focus", "study music",
        "1 hour", "ambient", "meditation", "generative art", "mathrelaxing",
        "python", "geometry", "S3", "linked circles", "focus music",
        "math art", "visualization",
    ]

    print(f"Subiendo: {video_path}...")
    print(f"Miniatura: {thumbnail_path}")
    print("Esto puede tardar (video ~5 GB).")

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
