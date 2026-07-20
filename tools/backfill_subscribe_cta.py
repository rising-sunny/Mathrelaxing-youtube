"""Backfill del CTA de suscripcion en las descripciones ya publicadas.

Motivo (2026-07): el catalogo publicado sigue generando ~8.4k vistas cada 28
dias, pero ninguna descripcion pedia la suscripcion (0 de 16 upload scripts la
incluian). El CTA nuevo solo aplica a subidas futuras; esto lo lleva al tráfico
que ya existe hoy.

Es **idempotente**: salta los videos cuya descripcion ya pide la suscripcion.
Es **aditivo**: antepone una linea y deja el resto de la descripcion, la tienda
y los hashtags intactos. Preserva titulo, tags, categoria e idiomas.

    python tools/backfill_subscribe_cta.py                    # dry-run, no escribe
    python tools/backfill_subscribe_cta.py --limit 1 --apply  # probar en 1 video
    python tools/backfill_subscribe_cta.py --apply            # aplicar a todos
    python tools/backfill_subscribe_cta.py --only-id VIDEOID --apply
"""

from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from metadata import ensure_subscribe_cta, has_subscribe_cta  # noqa: E402
from youtube_uploader import _build_youtube_service  # noqa: E402


def _uploads_playlist_id(youtube) -> str:
    resp = youtube.channels().list(part="contentDetails", mine=True).execute()
    items = resp.get("items") or []
    if not items:
        raise RuntimeError("No se pudo resolver el canal autenticado")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def _all_video_ids(youtube, playlist_id: str) -> list[str]:
    ids: list[str] = []
    page = None
    while True:
        resp = youtube.playlistItems().list(
            part="contentDetails", playlistId=playlist_id,
            maxResults=50, pageToken=page,
        ).execute()
        for it in resp.get("items", []):
            vid = it.get("contentDetails", {}).get("videoId")
            if vid:
                ids.append(vid)
        page = resp.get("nextPageToken")
        if not page:
            break
    return ids


def _fetch_snippets(youtube, video_ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        resp = youtube.videos().list(part="snippet", id=",".join(chunk)).execute()
        for it in resp.get("items", []):
            out[it["id"]] = it["snippet"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Escribir los cambios (por defecto dry-run)")
    ap.add_argument("--limit", type=int, default=None, help="Procesar como maximo N videos que necesiten cambio")
    ap.add_argument("--only-id", default=None, help="Actualizar un unico video por ID")
    a = ap.parse_args()

    youtube, _, channel_name = _build_youtube_service(desired_channel="MathRelaxing")
    print(f"Canal autenticado: {channel_name}")

    if a.only_id:
        video_ids = [a.only_id]
    else:
        video_ids = _all_video_ids(youtube, _uploads_playlist_id(youtube))
    print(f"Videos en el canal: {len(video_ids)}")

    snippets = _fetch_snippets(youtube, video_ids)
    print(f"Snippets obtenidos: {len(snippets)}")

    need = [(vid, sn) for vid, sn in snippets.items() if not has_subscribe_cta(sn.get("description", ""))]
    already = len(snippets) - len(need)
    print(f"Ya piden suscripcion: {already} | Necesitan CTA: {len(need)}\n")

    if a.limit is not None:
        need = need[:a.limit]

    changed = 0
    for vid, sn in need:
        old = sn.get("description", "")
        new = ensure_subscribe_cta(old)
        title = sn.get("title", "")
        print(f"[{vid}] {title[:58]}")
        if not a.apply:
            print(f"    + {new.splitlines()[0][:96]}")
            continue

        body_snippet = {
            "title": title,
            "categoryId": sn.get("categoryId", "28"),
            "description": new,
        }
        if sn.get("tags"):
            body_snippet["tags"] = sn["tags"]
        if sn.get("defaultLanguage"):
            body_snippet["defaultLanguage"] = sn["defaultLanguage"]
        if sn.get("defaultAudioLanguage"):
            body_snippet["defaultAudioLanguage"] = sn["defaultAudioLanguage"]

        youtube.videos().update(part="snippet", body={"id": vid, "snippet": body_snippet}).execute()
        changed += 1
        print("    actualizado")

    if a.apply:
        print(f"\nListo. Actualizados: {changed}")
    else:
        print(f"\nDRY-RUN: {len(need)} videos se actualizarian. Re-corre con --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
