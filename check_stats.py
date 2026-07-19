import sys
import os

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(REPO, "tools"))

try:
    from youtube_uploader import _build_youtube_service
except ImportError as e:
    print(f"Error importing: {e}")
    sys.exit(1)

def main():
    try:
        youtube, _, _ = _build_youtube_service(desired_channel='MathRelaxing')
        video_id = 'L39JRePtHF0'
        response = youtube.videos().list(part='statistics,snippet', id=video_id).execute()
        
        if not response.get('items'):
            print('Video no encontrado.')
            return
            
        item = response['items'][0]
        stats = item['statistics']
        snippet = item['snippet']
        
        print(f"Título: {snippet['title']}")
        print(f"Vistas: {stats.get('viewCount', 0)}")
        print(f"Likes: {stats.get('likeCount', 0)}")
        print(f"Comentarios: {stats.get('commentCount', 0)}")
    except Exception as e:
        print(f"Error checking stats: {e}")

if __name__ == "__main__":
    main()
