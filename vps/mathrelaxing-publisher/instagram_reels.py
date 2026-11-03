import argparse
import fcntl
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from uuid import UUID

import requests

IG = "17841424433432565"
GRAPH = "https://graph.facebook.com/v23.0"
PUBLIC = "https://publisher.mathrelaxing.store"
ROOT = Path("/var/lib/mathrelaxing-publisher")
STATE = Path("/var/lib/mathrelaxing-publisher-cli")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["publicar", "seguimiento"])
    parser.add_argument("id", type=UUID)
    parser.add_argument("--instagram", action="store_true", required=True)
    args = parser.parse_args()

    job = str(args.id)
    folder = ROOT / job
    draft = json.loads((folder / "draft.json").read_text())
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    journal = STATE / (job + "-instagram.json")

    credentials = Path("/etc/mathrelaxing-publisher")
    token = (credentials / "meta-token").read_text().strip()
    headers = {"Authorization": "Bearer " + token}

    def save(record):
        temporary = journal.with_suffix(".tmp")
        temporary.write_text(json.dumps(record))
        os.replace(temporary, journal)

    def api(method, endpoint, **kwargs):
        response = requests.request(
            method, GRAPH + endpoint, headers=headers,
            timeout=(30, 120), **kwargs
        )
        data = response.json()
        if not response.ok or "error" in data:
            error = data.get("error", {})
            print("Meta HTTP:", response.status_code,
                  "| Código:", error.get("code"),
                  "| Subcódigo:", error.get("error_subcode"))
            raise RuntimeError("Meta rechazó la operación.")
        return data

    with (STATE / (job + "-instagram.lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record = json.loads(journal.read_text()) if journal.exists() else {}

        if args.action == "seguimiento":
            print("Etapa local:", record.get("stage", "sin intento"))
            if record.get("media_id"):
                media = api("GET", "/" + record["media_id"],
                            params={"fields": "id,permalink"})
                print("Publicación:", media.get("permalink"))
            elif record.get("container_id"):
                container = api(
                    "GET", "/" + record["container_id"],
                    params={"fields": "id,status_code"},
                )
                print("Contenedor:", container.get("id"))
                print("Estado Meta:", container.get("status_code"))
            return

        if record.get("stage") in {
            "creating", "publishing", "needs_review", "published"
        }:
            print("No se repetirá este intento.")
            print("Etapa:", record["stage"])
            print("Consulta seguimiento antes de tomar otra acción.")
            return

        if draft["title"].strip().lower() == "connection test":
            raise RuntimeError("El borrador de prueba no se puede publicar.")
        if not (folder / "video.mp4").is_file():
            raise RuntimeError("El borrador no tiene video.")

        identity = api("GET", "/" + IG, params={"fields": "id,username"})
        if (str(identity.get("id")) != IG
                or identity.get("username", "").lower() != "mathrelaxing"):
            raise RuntimeError("La cuenta de destino no coincide.")

        try:
            if not record.get("container_id"):
                key = (credentials / "api-key").read_text().strip()
                expires = int(time.time()) + 86400
                signature = hmac.new(
                    key.encode(), f"{job}:{expires}".encode(),
                    hashlib.sha256,
                ).hexdigest()
                video_url = f"{PUBLIC}/media/{job}/{expires}/{signature}"

                with requests.get(
                    video_url, headers={"Range": "bytes=0-31"},
                    stream=True, timeout=30,
                ) as check:
                    check.raise_for_status()
                    sample = next(check.iter_content(32), b"")
                    if b"ftyp" not in sample:
                        raise RuntimeError("No se pudo verificar el MP4 público.")

                record = {"stage": "creating"}
                save(record)
                container = api("POST", "/" + IG + "/media", data={
                    "media_type": "REELS",
                    "video_url": video_url,
                    "caption": draft["instagram_caption"],
                    "share_to_feed": "true",
                })
                record["container_id"] = str(container["id"])
                record["stage"] = "processing"
                save(record)

            for _ in range(12):
                container = api(
                    "GET", "/" + record["container_id"],
                    params={"fields": "id,status_code"},
                )
                status = container.get("status_code")
                if status == "FINISHED":
                    break
                if status in {"ERROR", "EXPIRED", "PUBLISHED"}:
                    record["stage"] = "needs_review"
                    save(record)
                    print("Estado del contenedor:", status)
                    return
                time.sleep(5)
            else:
                print("Instagram sigue procesando el video.")
                print("Puedes consultar seguimiento y repetir publicar")
                print("cuando termine; se reutilizará el mismo contenedor.")
                return

            record["stage"] = "publishing"
            save(record)
            result = api("POST", "/" + IG + "/media_publish", data={
                "creation_id": record["container_id"],
            })
            record["media_id"] = str(result["id"])
            record["stage"] = "published"
            save(record)
            print("Instagram confirmó la publicación.")
            print("ID:", record["media_id"])
            print("Usa seguimiento para obtener el enlace.")

        except Exception:
            if record:
                record["previous_stage"] = record.get("stage")
                record["stage"] = "needs_review"
                save(record)
            print("Intento detenido. No se reintentará automáticamente.")
            raise SystemExit(1)


if __name__ == "__main__":
    os.umask(0o077)
    try:
        main()
    except (OSError, ValueError, RuntimeError, requests.RequestException):
        raise SystemExit("No se completó la operación; no se muestran secretos.")
