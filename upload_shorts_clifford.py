"""Upload Clifford Torus 10s Short to MathRelaxing."""
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
    video_path = os.path.join(REPO, "output", "shorts_clifford", "shorts_clifford.mp4")

    if not os.path.exists(video_path):
        print(f"Error: No se encontró el video {video_path}")
        sys.exit(1)

    title = (
        "Clifford Torus 4D — A Flat Torus in S³ ✨ T² ⊂ S³ ⊂ ℝ⁴ "
        "#math #shorts #geometry"
    )
    description = (
        "A flat torus living in 4D space: the Clifford torus T² ⊂ S³ ⊂ ℝ⁴, "
        "stereographically projected into 3D.\n\n"
        "Watch the hyperspace shadow rotate — continuous 4D motion, seamless loop.\n\n"
        "Full 1 HOUR version: https://youtu.be/6QO8z8NuKgA\n\n"
        "✨ Math-inspired designs: https://mathrelaxing.store\n\n"
        "#MathRelaxing #CliffordTorus #4D #Topology #Geometry #Shorts "
        "#MathArt #GenerativeArt #DeepFocus #StudyMusic"
    )
    tags = [
        "math", "clifford torus", "4D", "shorts", "topology", "geometry",
        "mathrelaxing", "generative art", "S3", "math art", "python",
    ]

    print(f"Subiendo: {video_path}...")

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
    )
    print(f"\n\n¡Subida completada en '{channel_name}'!")
    print(f"PÚBLICO: https://youtu.be/{video_id}")
    return video_id


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n\nError al subir: {e}")
        sys.exit(1)
