"""MCP de solo lectura con las metricas del canal MathRelaxing (YouTube Data + Analytics).

Requiere: pip install "mcp>=1.13,<2" google-api-python-client google-auth-oauthlib
(mcp 2.x renombro FastMCP; no usar). Autenticacion OAuth en yt_metrics_oauth.py.
Autorizar (una vez):  python yt_metrics_mcp.py --auth
Servir:               python yt_metrics_mcp.py

Variables de entorno:
  YT_METRICS_CLIENT_SECRET  ruta al client_secret.json (default ./client_secret.json)
  YT_METRICS_TOKEN_FILE     ruta del token readonly   (default ./token_yt_metrics.json)
  MCP_OWNER_PASSWORD        contrasena que escribes al autorizar la conexion (obligatorio)
  MCP_OAUTH_STORE           JSON con clientes/tokens OAuth (default ./oauth_store.json)
  MCP_ALLOWED_HOST          dominio publico, sin https:// (obligatorio); el MCP queda en /mcp
  MCP_PORT                  puerto local (default 8765, escucha solo en 127.0.0.1)
"""
import os
import sys
from datetime import date, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
CLIENT_SECRET = os.environ.get("YT_METRICS_CLIENT_SECRET", "client_secret.json")
TOKEN_FILE = os.environ.get("YT_METRICS_TOKEN_FILE", "token_yt_metrics.json")
VIDEO_METRICS = (
    "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
    "likes,comments,shares,subscribersGained,subscribersLost"
)


def _creds() -> Credentials:
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())
    return creds


def _data():
    return build("youtube", "v3", credentials=_creds(), cache_discovery=False)


def _analytics():
    return build("youtubeAnalytics", "v2", credentials=_creds(), cache_discovery=False)


def _range(days: int) -> dict:
    end = date.today() - timedelta(days=1)  # Analytics va ~1-2 dias atrasado
    return {"startDate": str(end - timedelta(days=days - 1)), "endDate": str(end)}


def _rows(resp: dict) -> list[dict]:
    heads = [h["name"] for h in resp.get("columnHeaders", [])]
    return [dict(zip(heads, r)) for r in resp.get("rows", [])]


def build_server():
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings

    from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
    from yt_metrics_oauth import SCOPE, OwnerOAuthProvider, register_approval_routes

    host = os.environ["MCP_ALLOWED_HOST"]
    base = f"https://{host}"
    provider = OwnerOAuthProvider(os.environ.get("MCP_OAUTH_STORE", "oauth_store.json"), base)
    mcp = FastMCP(
        "mathrelaxing-youtube-metrics",
        host="127.0.0.1",
        port=int(os.environ.get("MCP_PORT", "8765")),
        streamable_http_path="/mcp",
        stateless_http=True,
        auth_server_provider=provider,
        auth=AuthSettings(
            issuer_url=base,
            resource_server_url=f"{base}/mcp",
            required_scopes=[SCOPE],
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]),
            revocation_options=RevocationOptions(enabled=True),
        ),
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[host, f"{host}:*"],
            allowed_origins=[f"https://{host}"],
        ),
    )

    register_approval_routes(mcp, provider, os.environ["MCP_OWNER_PASSWORD"])

    @mcp.tool()
    def yt_channel_overview(days: int = 28) -> dict:
        """Totales del canal (suscriptores, vistas historicas) y metricas de los ultimos N dias."""
        ch = _data().channels().list(part="snippet,statistics", mine=True).execute()["items"][0]
        period = _analytics().reports().query(
            ids="channel==MINE", metrics=VIDEO_METRICS, **_range(days)
        ).execute()
        return {
            "channel": ch["snippet"]["title"],
            "lifetime": ch["statistics"],
            "period_days": days,
            "period": (_rows(period) or [{}])[0],
        }

    @mcp.tool()
    def yt_recent_videos(limit: int = 10) -> list[dict]:
        """Ultimos videos subidos con sus estadisticas publicas (vistas, likes, comentarios)."""
        yt = _data()
        uploads = yt.channels().list(part="contentDetails", mine=True).execute()[
            "items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        items = yt.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=min(limit, 50)
        ).execute()["items"]
        ids = ",".join(i["contentDetails"]["videoId"] for i in items)
        vids = yt.videos().list(part="snippet,statistics,status", id=ids).execute()["items"]
        return [
            {
                "id": v["id"],
                "title": v["snippet"]["title"],
                "published_at": v["snippet"]["publishedAt"],
                "privacy": v["status"]["privacyStatus"],
                "stats": v["statistics"],
            }
            for v in vids
        ]

    @mcp.tool()
    def yt_video_metrics(video_id: str, days: int = 28) -> dict:
        """Analytics de un video: vistas, minutos vistos, duracion y % promedio visto, suscriptores ganados."""
        resp = _analytics().reports().query(
            ids="channel==MINE", metrics=VIDEO_METRICS,
            filters=f"video=={video_id}", **_range(days),
        ).execute()
        return {"video_id": video_id, "period_days": days, "metrics": (_rows(resp) or [{}])[0]}

    @mcp.tool()
    def yt_top_videos(days: int = 28, limit: int = 10, sort_by: str = "views") -> list[dict]:
        """Ranking de videos en los ultimos N dias. sort_by: views, estimatedMinutesWatched, subscribersGained, averageViewPercentage."""
        resp = _analytics().reports().query(
            ids="channel==MINE", dimensions="video", metrics=VIDEO_METRICS,
            sort=f"-{sort_by}", maxResults=min(limit, 50), **_range(days),
        ).execute()
        return _rows(resp)

    @mcp.tool()
    def yt_traffic_sources(days: int = 28) -> list[dict]:
        """De donde viene la audiencia (Shorts feed, busqueda, sugeridos, etc.)."""
        resp = _analytics().reports().query(
            ids="channel==MINE", dimensions="insightTrafficSourceType",
            metrics="views,estimatedMinutesWatched", sort="-views", **_range(days),
        ).execute()
        return _rows(resp)

    return mcp


def authorize():
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
    # VPS sin navegador: abre un tunel  ssh -L 8080:localhost:8080 root@VPS  y pega la URL en tu PC.
    creds = flow.run_local_server(port=8080, open_browser=False, access_type="offline", prompt="consent")
    with open(TOKEN_FILE, "w", encoding="utf-8") as fh:
        fh.write(creds.to_json())
    os.chmod(TOKEN_FILE, 0o600)
    print(f"Token guardado en {TOKEN_FILE}")


if __name__ == "__main__":
    if "--auth" in sys.argv:
        authorize()
    else:
        build_server().run(transport="streamable-http")
