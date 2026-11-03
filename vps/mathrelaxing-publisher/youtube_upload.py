import argparse
import fcntl
import json
import os
import tempfile
from pathlib import Path
from uuid import UUID

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CHANNEL = "UCn8REDiVrUNYYVoPLSkXWqQ"
ROOT = Path("/var/lib/mathrelaxing-publisher")
STATE = Path("/var/lib/mathrelaxing-publisher-cli")
TOKEN = Path("/etc/mathrelaxing-publisher/youtube-token.json")


def atomic_json(path, data):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".youtube-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["publicar", "seguimiento"])
    parser.add_argument("id", type=UUID)
    parser.add_argument("--youtube", action="store_true", required=True)
    parser.add_argument(
        "--privacidad", choices=["private", "unlisted", "public"],
        default="private"
    )
    args = parser.parse_args()
    job = str(args.id)
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    journal = STATE / (job + "-youtube.json")

    credentials = Credentials.from_authorized_user_file(str(TOKEN))
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        atomic_json(TOKEN, json.loads(credentials.to_json()))
    youtube = build("youtube", "v3", credentials=credentials,
                    cache_discovery=False)

    channels = youtube.channels().list(part="id", mine=True).execute()
    if {item["id"] for item in channels.get("items", [])} != {CHANNEL}:
        raise RuntimeError("El canal autorizado no coincide con MathRelaxing.")

    with (STATE / (job + "-youtube.lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = json.loads(journal.read_text()) if journal.exists() else {}

        if args.action == "seguimiento":
            if not record.get("video_id"):
                print("Sin ID confirmado. Etapa:", record.get("stage", "sin intento"))
                return
            result = youtube.videos().list(
                part="snippet,status,processingDetails",
                id=record["video_id"],
            ).execute()
            for item in result.get("items", []):
                print("Título:", item["snippet"]["title"])
                print("Privacidad:", item["status"].get("privacyStatus"))
                print("Estado de subida:", item["status"].get("uploadStatus"))
                print("Procesamiento:", item.get(
                    "processingDetails", {}).get("processingStatus", "no informado"))
                print("Enlace: https://www.youtube.com/watch?v=" + item["id"])
            return

        if record:
            print("Ya existe un intento; no se repetirá la subida.")
            print("Etapa:", record.get("stage"))
            print("Consulta seguimiento o revisa YouTube Studio.")
            return

        folder = ROOT / job
        draft = json.loads((folder / "draft.json").read_text())
        video = folder / "video.mp4"
        if not video.is_file():
            raise RuntimeError("El borrador no tiene video.")
        if (draft["title"].strip().lower() == "connection test"
                and args.privacidad != "private"):
            raise RuntimeError("El video de prueba solo puede subirse privado.")

        description = draft.get("youtube_description") or draft["facebook_caption"]
        record = {"stage": "uploading", "requested_privacy": args.privacidad}
        atomic_json(journal, record)

        try:
            upload = youtube.videos().insert(
                part="snippet,status",
                notifySubscribers=False,
                body={
                    "snippet": {
                        "title": draft["title"],
                        "description": description,
                        "categoryId": "28",
                    },
                    "status": {
                        "privacyStatus": args.privacidad,
                        "selfDeclaredMadeForKids": False,
                    },
                },
                media_body=MediaFileUpload(
                    str(video), mimetype="video/mp4",
                    chunksize=8 * 1024 * 1024, resumable=True,
                ),
            )
            result = None
            while result is None:
                progress, result = upload.next_chunk(num_retries=0)
                if progress:
                    print("Carga:", round(progress.progress() * 100), "%")
            record["video_id"] = result["id"]
            record["stage"] = "uploaded"
            atomic_json(journal, record)
            print("YouTube confirmó la carga.")
            print("Privacidad solicitada:", args.privacidad)
            print("Enlace: https://www.youtube.com/watch?v=" + result["id"])
            print("Consulta seguimiento para verificar privacidad y procesamiento.")
        except Exception:
            record["stage"] = "needs_review"
            atomic_json(journal, record)
            print("Resultado incompleto o incierto; no se reintentará automáticamente.")
            print("Revisa YouTube Studio antes de iniciar otra subida.")
            raise SystemExit(1)


if __name__ == "__main__":
    os.umask(0o077)
    try:
        main()
    except Exception:
        raise SystemExit("Falló la operación; no se muestran credenciales.")
