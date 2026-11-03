import argparse
import fcntl
import json
import os
from pathlib import Path
from uuid import UUID

import requests

PAGE = "1039054555956731"
GRAPH = "https://graph.facebook.com/v23.0"
ROOT = Path("/var/lib/mathrelaxing-publisher")
STATE = Path("/var/lib/mathrelaxing-publisher-cli")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["publicar", "seguimiento"])
    parser.add_argument("id", type=UUID)
    parser.add_argument("--facebook", action="store_true", required=True)
    args = parser.parse_args()

    job = str(args.id)
    folder = ROOT / job
    draft = json.loads((folder / "draft.json").read_text())
    journal = STATE / (job + "-facebook.json")
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)

    token = Path(
        "/etc/mathrelaxing-publisher/facebook-page-token"
    ).read_text().strip()
    headers = {"Authorization": "Bearer " + token}

    def save(data):
        temporary = journal.with_suffix(".tmp")
        temporary.write_text(json.dumps(data))
        os.replace(temporary, journal)

    def check(response):
        data = response.json()
        if not response.ok or "error" in data:
            error = data.get("error", {})
            print("Meta HTTP:", response.status_code,
                  "| Código:", error.get("code"),
                  "| Subcódigo:", error.get("error_subcode"))
            raise RuntimeError("Meta rechazó la operación.")
        return data

    with (STATE / (job + "-facebook.lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = json.loads(journal.read_text()) if journal.exists() else {}

        if args.action == "seguimiento":
            if not record.get("video_id"):
                print("No hay ID de video registrado.")
                print("Estado:", record.get("stage", "sin intento"))
                return
            response = requests.get(
                GRAPH + "/" + record["video_id"],
                headers=headers,
                params={"fields": "id,status"},
                timeout=30,
            )
            data = check(response)
            print(json.dumps(data, indent=2))
            print("ID de video:", record["video_id"])
            print("Última etapa local:", record.get("stage"))
            return

        if record:
            print("Ya existe un intento. No se repetirá la publicación.")
            print("Estado:", record.get("stage"))
            print("Consulta con: mathrelaxing-publish seguimiento",
                  job, "--facebook")
            return

        if draft["title"].strip().lower() == "connection test":
            raise RuntimeError("El borrador de prueba no se puede publicar.")
        if not (folder / "video.mp4").is_file():
            raise RuntimeError("El borrador no tiene video.")

        record = {"stage": "starting"}
        save(record)
        try:
            data = check(requests.post(
                GRAPH + "/" + PAGE + "/video_reels",
                headers=headers,
                data={"upload_phase": "start"},
                timeout=60,
            ))
            record["video_id"] = str(data["video_id"])
            record["stage"] = "uploading"
            save(record)

            from urllib.parse import urlparse
            upload_url = data["upload_url"]
            parsed = urlparse(upload_url)
            if (parsed.scheme != "https"
                    or parsed.hostname != "rupload.facebook.com"
                    or parsed.username or parsed.password
                    or parsed.port not in (None, 443)):
                raise RuntimeError("Destino de carga inesperado.")

            video = folder / "video.mp4"
            with video.open("rb") as stream:
                result = check(requests.post(
                    upload_url,
                    headers={
                        **headers,
                        "offset": "0",
                        "file_size": str(video.stat().st_size),
                        "Content-Type": "application/octet-stream",
                    },
                    data=stream,
                    timeout=(30, 600),
                    allow_redirects=False,
                ))
            if result.get("success") is not True:
                raise RuntimeError("La carga no fue confirmada.")

            record["stage"] = "finishing"
            save(record)
            result = check(requests.post(
                GRAPH + "/" + PAGE + "/video_reels",
                headers=headers,
                data={
                    "upload_phase": "finish",
                    "video_id": record["video_id"],
                    "video_state": "PUBLISHED",
                    "title": draft["title"],
                    "description": draft["facebook_caption"],
                },
                timeout=120,
            ))
            if result.get("success") is not True:
                raise RuntimeError("Meta no confirmó el envío final.")
            record["stage"] = "submitted"
            save(record)
            print("Enviado a Facebook; procesamiento pendiente de comprobar.")
            print("ID de video:", record["video_id"])
        except Exception:
            record["previous_stage"] = record["stage"]
            record["stage"] = "needs_review"
            save(record)
            print("Intento detenido; no se reintentará automáticamente.")
            print("Consulta seguimiento antes de tomar otra acción.")
            raise SystemExit(1)


if __name__ == "__main__":
    os.umask(0o077)
    try:
        main()
    except (OSError, ValueError, RuntimeError, requests.RequestException):
        raise SystemExit("No se completó la operación. No se muestran secretos.")
