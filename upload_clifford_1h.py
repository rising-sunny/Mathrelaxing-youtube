"""Upload Clifford Torus 4D 1h video + thumbnail to MathRelaxing."""
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
    video_path = os.path.join(REPO, "output", "clifford_1h", "clifford_1h_final.mp4")
    thumbnail_path = os.path.join(REPO, "output", "clifford_1h", "clifford_thumbnail_text.jpg")

    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)
    if not os.path.exists(thumbnail_path):
        print(f"Error: No se encontró el thumbnail {thumbnail_path}")
        sys.exit(1)

    title = (
        "1 HOUR Deep Focus ✨ Clifford Torus 4D — Flat Torus in S³ "
        "(T² ⊂ S³ ⊂ ℝ⁴) #math #study #geometry"
    )
    description = (
        "Dive into deep focus with 1 hour of the Clifford torus — the flattest "
        "torus embedded in the 3-sphere: T² ⊂ S³ ⊂ ℝ⁴.\n\n"
        "Watch 28,800 glowing points trace the product of two circles in orthogonal "
        "planes of 4D space, then stereographically projected into 3D. Continuous "
        "4D rotations (xy, zw, yz) and surface phase drift create a seamless "
        "hyperspace loop with a full 360° camera orbit.\n\n"
        "Math note: the Clifford torus is a minimal surface in S³ and a flat "
        "metric torus — every point has zero Gaussian curvature in the intrinsic "
        "geometry, yet its shadow in ℝ³ becomes the classic donut of linked "
        "circles you see here.\n\n"
        "🎧 Ambient focus soundscape with generative sonification, drone, and "
        "concentration-friendly tracks. Perfect for studying, coding, reading, "
        "or meditation.\n\n"
        "✨ Discover mathematics-inspired designs and support the channel: "
        "https://mathrelaxing.store\n\n"
        "#MathRelaxing #CliffordTorus #4D #Topology #Geometry #DeepFocus "
        "#StudyMusic #Ambient #MathArt #GenerativeArt #Python #S3 #Meditation"
    )
    tags = [
        "math", "clifford torus", "4D", "topology", "geometry", "deep focus",
        "study music", "1 hour", "ambient", "meditation", "generative art",
        "mathrelaxing", "python", "S3", "hypersphere", "focus music",
        "math art", "visualization",
    ]

    print(f"Subiendo: {video_path}...")
    print(f"Miniatura: {thumbnail_path}")
    print("Esto puede tardar (video ~2.8 GB).")

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
