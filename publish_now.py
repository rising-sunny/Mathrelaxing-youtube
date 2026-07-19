import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

from youtube_uploader import _build_youtube_service

def main():
    try:
        youtube, _, _ = _build_youtube_service(desired_channel="MathRelaxing")
        video_id = "3uHPqxH9Uu0"
        
        print(f"Buscando video {video_id}...")
        
        request = youtube.videos().update(
            part="status",
            body={
                "id": video_id,
                "status": {
                    "privacyStatus": "public"
                }
            }
        )
        response = request.execute()
        
        print("¡Video publicado exitosamente!")
        print(f"Estado actual: {response['status']['privacyStatus']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
