import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

try:
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
    thumb_path = r"C:\Users\sunse\.gemini\antigravity\brain\3e24b39e-9a8d-491e-a653-8cd9f3d3adc2\thomas_thumbnail_text.jpg"
    
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
