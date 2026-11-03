"""Registro de vistas por video para ver la curva real de las primeras horas.

Analytics solo da datos diarios y con 2-3 dias de retraso. Este modulo guarda en SQLite las
vistas publicas de los videos publicados en las ultimas 72 h: cada 15 min durante las primeras
6 h y cada ~1 h despues. Lo lanza un timer de systemd:   python yt_snapshots.py
Las herramientas del MCP leen la base con view_curve().

Variable: YT_METRICS_DB (default: snapshots.db junto al token por defecto).
"""
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

TRACK_HOURS = 72
DENSE_HOURS = 6
DENSE_GAP, SPARSE_GAP = 10 * 60, 55 * 60  # segundos minimos entre snapshots del mismo video
SCHEMA = """
CREATE TABLE IF NOT EXISTS videos(video_id TEXT PRIMARY KEY, channel TEXT, title TEXT, published_at INTEGER);
CREATE TABLE IF NOT EXISTS snaps(video_id TEXT, ts INTEGER, views INTEGER, likes INTEGER, comments INTEGER);
CREATE INDEX IF NOT EXISTS snaps_v ON snaps(video_id, ts);
"""


def db_path() -> Path:
    env = os.environ.get("YT_METRICS_DB")
    if env:
        return Path(env)
    token = os.environ.get("YT_METRICS_TOKEN_FILE", "token_yt_metrics.json")
    return Path(token).resolve().parent / "snapshots.db"


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(db_path(), timeout=30)
    con.executescript(SCHEMA)
    return con


def _epoch(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def record(con: sqlite3.Connection, channel: str, items: list[dict], now: int) -> int:
    """Guarda un snapshot por video dentro de la ventana de seguimiento. Devuelve cuantos guardo."""
    saved = 0
    for v in items:
        pub = _epoch(v["published_at"])
        age = now - pub
        if age < 0 or age > TRACK_HOURS * 3600:
            continue
        con.execute(
            "INSERT INTO videos(video_id, channel, title, published_at) VALUES (?,?,?,?) "
            "ON CONFLICT(video_id) DO UPDATE SET title=excluded.title",
            (v["id"], channel, v["title"], pub),
        )
        last = con.execute("SELECT MAX(ts) FROM snaps WHERE video_id=?", (v["id"],)).fetchone()[0]
        gap = DENSE_GAP if age <= DENSE_HOURS * 3600 else SPARSE_GAP
        if last is not None and now - last < gap:
            continue
        con.execute("INSERT INTO snaps VALUES (?,?,?,?,?)",
                    (v["id"], now, v["views"], v["likes"], v["comments"]))
        saved += 1
    con.commit()
    return saved


def _fetch(m, channel: str) -> list[dict]:
    yt = m._data(channel)
    uploads = yt.channels().list(part="contentDetails", mine=True).execute()[
        "items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = [i["contentDetails"]["videoId"] for i in yt.playlistItems().list(
        part="contentDetails", playlistId=uploads, maxResults=10).execute()["items"]]
    if not ids:
        return []
    vids = yt.videos().list(part="snippet,statistics", id=",".join(ids)).execute()["items"]
    return [{
        "id": v["id"], "title": v["snippet"]["title"], "published_at": v["snippet"]["publishedAt"],
        "views": int(v["statistics"].get("viewCount", 0)),
        "likes": int(v["statistics"].get("likeCount", 0)),
        "comments": int(v["statistics"].get("commentCount", 0)),
    } for v in vids]


def main() -> int:
    import yt_metrics_mcp as m

    con = _connect()
    now = int(time.time())
    channels = m._channels()
    saved = errors = 0
    for ch in channels:
        try:
            saved += record(con, ch, _fetch(m, ch), now)
        except Exception as exc:  # noqa: BLE001 - un canal roto no debe frenar a los demas
            errors += 1
            print(f"[{ch}] error: {exc}", file=sys.stderr)
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%MZ} snapshots={saved} canales={len(channels)} errores={errors}")
    return 1 if channels and errors == len(channels) else 0


# --- lectura (la usa el MCP) ---
def _at(pts: list[tuple[int, int]], minutes: int):
    if pts[-1][0] < minutes:
        return None  # el video aun no llega a esa edad
    before = [v for t, v in pts if t <= minutes]
    return before[-1] if before else None  # None si el registro empezo despues de esa edad


def _t(pts: list[tuple[int, int]], frac: float):
    final = pts[-1][1]
    return next((t for t, v in pts if final and v >= frac * final), None)


def view_curve(video_id: str) -> dict | None:
    path = db_path()
    if not path.exists():
        return None
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    try:
        meta = con.execute("SELECT title, published_at, channel FROM videos WHERE video_id=?",
                           (video_id,)).fetchone()
        rows = con.execute("SELECT ts, views FROM snaps WHERE video_id=? ORDER BY ts",
                           (video_id,)).fetchall()
    finally:
        con.close()
    if not meta or not rows:
        return None
    title, pub, channel = meta
    pts = [((ts - pub) // 60, views) for ts, views in rows]
    return {
        "video_id": video_id, "title": title, "channel": channel,
        "published_at": datetime.fromtimestamp(pub, timezone.utc).isoformat(),
        "snapshots": len(pts), "first_snapshot_min": pts[0][0], "age_min": pts[-1][0],
        "views_now": pts[-1][1],
        "checkpoints": {f"{h}h": _at(pts, h * 60) for h in (1, 3, 6, 12, 24, 48)},
        "t50_min": _t(pts, 0.5), "t90_min": _t(pts, 0.9),
        "curve": [[t, v] for t, v in pts],
    }


if __name__ == "__main__":
    sys.exit(main())
