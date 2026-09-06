import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

try:
    from paths import thumbnail_path
    from youtube_uploader import _build_youtube_service
    from googleapiclient.http import MediaFileUpload
except ImportError as e:
    print("Error imports:", e)
    sys.exit(1)

def main():
    try:
        youtube, _, _ = _build_youtube_service(desired_channel="MathRelaxing")
    except Exception as e:
        print("Auth Failed:", e)
        sys.exit(1)
        
    video_id = "Evt6KIxr7DA"
    thumb_path = thumbnail_path("thomas_thumbnail_text.jpg", create=False)
    
    if not os.path.isfile(thumb_path):
        sys.exit(f"No se encontro la miniatura: {thumb_path}")

    print(f"Setting thumbnail for {video_id}...")
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumb_path)
        ).execute()
        print("Success")
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    main()
