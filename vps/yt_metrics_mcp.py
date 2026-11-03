"""MCP de solo lectura con las metricas del canal MathRelaxing (YouTube Data + Analytics).

Requiere: pip install "mcp>=1.13,<2" google-api-python-client google-auth-oauthlib
(mcp 2.x renombro FastMCP; no usar). Autenticacion OAuth en yt_metrics_oauth.py.
Autorizar (una vez):  python yt_metrics_mcp.py --auth
Servir:               python yt_metrics_mcp.py

Variables de entorno:
  YT_METRICS_CLIENT_SECRET  ruta al client_secret.json (default ./client_secret.json)
  YT_METRICS_TOKEN_FILE     token del canal por defecto (default ./token_yt_metrics.json)
  YT_METRICS_DEFAULT_CHANNEL alias del canal por defecto (default mathrelaxing)
Canales extra: token_<alias>.json junto al token por defecto. Autorizar:  --auth --channel <alias>
  MCP_OWNER_PASSWORD        contrasena que escribes al autorizar la conexion (obligatorio)
  MCP_OAUTH_STORE           JSON con clientes/tokens OAuth (default ./oauth_store.json)
  MCP_ALLOWED_HOST          dominio publico, sin https:// (obligatorio); el MCP queda en /mcp
  MCP_PORT                  puerto local (default 8765, escucha solo en 127.0.0.1)
"""
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

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


DEFAULT_CHANNEL = os.environ.get("YT_METRICS_DEFAULT_CHANNEL", "mathrelaxing").strip().lower()
_ALIAS = re.compile(r"[a-z0-9_-]{1,40}")


def _alias(channel: str | None) -> str:
    alias = (channel or DEFAULT_CHANNEL).strip().lower()
    if not _ALIAS.fullmatch(alias):
        raise ValueError("Nombre de canal invalido: usa solo a-z, 0-9, - y _")
    return alias


def _token_path(channel: str | None) -> Path:
    alias = _alias(channel)
    if alias == DEFAULT_CHANNEL:
        return Path(TOKEN_FILE)
    return Path(TOKEN_FILE).parent / f"token_{alias}.json"


def _channels() -> list[str]:
    default = Path(TOKEN_FILE)
    found = {m.group(1) for f in default.parent.glob("token_*.json")
             if f.name != default.name and (m := re.fullmatch(r"token_([a-z0-9_-]{1,40})\.json", f.name))}
    if default.exists():
        found.add(DEFAULT_CHANNEL)
    return sorted(found)


def _creds(channel: str | None = None) -> Credentials:
    path = _token_path(channel)
    if not path.exists():
        raise ValueError(f"Canal '{_alias(channel)}' sin autorizar. Disponibles: {', '.join(_channels())}")
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _data(channel: str | None = None):
    return build("youtube", "v3", credentials=_creds(channel), cache_discovery=False)


def _analytics(channel: str | None = None):
    return build("youtubeAnalytics", "v2", credentials=_creds(channel), cache_discovery=False)


def _range(days: int) -> dict:
    end = date.today() - timedelta(days=1)  # Analytics va ~1-2 dias atrasado
    return {"startDate": str(end - timedelta(days=days - 1)), "endDate": str(end)}


_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


def _video(video_id: str) -> str:
    video_id = video_id.strip()
    if not _VIDEO_ID.fullmatch(video_id):
        raise ValueError("video_id invalido (11 caracteres: letras, numeros, - y _)")
    return video_id


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
            validate_token_resource=False,  # un unico servidor de autorizacion (el propio); sin cambio de comportamiento
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
    def yt_list_channels() -> list[dict]:
        """Canales autorizados (alias para el parametro `channel` de las demas herramientas) con su nombre real."""
        out = []
        for alias in _channels():
            try:
                title = _data(alias).channels().list(part="snippet", mine=True).execute()["items"][0]["snippet"]["title"]
            except Exception as exc:  # noqa: BLE001
                title = f"error: {exc}"
            out.append({"channel": alias, "title": title, "default": alias == DEFAULT_CHANNEL})
        return out

    @mcp.tool()
    def yt_channel_overview(days: int = 28, channel: str = "") -> dict:
        """Totales del canal (suscriptores, vistas historicas) y metricas de los ultimos N dias. `channel`: alias (ver yt_list_channels); vacio = canal por defecto."""
        ch = _data(channel).channels().list(part="snippet,statistics", mine=True).execute()["items"][0]
        period = _analytics(channel).reports().query(
            ids="channel==MINE", metrics=VIDEO_METRICS, **_range(days)
        ).execute()
        return {
            "channel": ch["snippet"]["title"],
            "lifetime": ch["statistics"],
            "period_days": days,
            "period": (_rows(period) or [{}])[0],
        }

    @mcp.tool()
    def yt_recent_videos(limit: int = 10, channel: str = "") -> list[dict]:
        """Ultimos videos subidos con sus estadisticas publicas (vistas, likes, comentarios). `channel`: alias; vacio = por defecto."""
        yt = _data(channel)
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
    def yt_video_metrics(video_id: str, days: int = 28, channel: str = "") -> dict:
        """Analytics de un video: vistas, minutos vistos, duracion y % promedio visto, suscriptores ganados. `channel`: alias del canal dueno del video."""
        resp = _analytics(channel).reports().query(
            ids="channel==MINE", metrics=VIDEO_METRICS,
            filters=f"video=={_video(video_id)}", **_range(days),
        ).execute()
        return {"video_id": video_id, "period_days": days, "metrics": (_rows(resp) or [{}])[0]}

    @mcp.tool()
    def yt_top_videos(days: int = 28, limit: int = 10, sort_by: str = "views", channel: str = "") -> list[dict]:
        """Ranking de videos en los ultimos N dias. sort_by: views, estimatedMinutesWatched, subscribersGained, averageViewPercentage. `channel`: alias; vacio = por defecto."""
        resp = _analytics(channel).reports().query(
            ids="channel==MINE", dimensions="video", metrics=VIDEO_METRICS,
            sort=f"-{sort_by}", maxResults=min(limit, 50), **_range(days),
        ).execute()
        return _rows(resp)

    @mcp.tool()
    def yt_traffic_sources(days: int = 28, channel: str = "") -> list[dict]:
        """De donde viene la audiencia (Shorts feed, busqueda, sugeridos, etc.). `channel`: alias; vacio = por defecto."""
        resp = _analytics(channel).reports().query(
            ids="channel==MINE", dimensions="insightTrafficSourceType",
            metrics="views,estimatedMinutesWatched", sort="-views", **_range(days),
        ).execute()
        return _rows(resp)

    @mcp.tool()
    def yt_video_daily(video_id: str, days: int = 14, channel: str = "") -> list[dict]:
        """Vistas dia a dia de un video (curva de decaimiento): vistas, minutos vistos, % visto, likes, suscriptores. Muestra cuando se frena. `channel`: alias."""
        resp = _analytics(channel).reports().query(
            ids="channel==MINE", dimensions="day", sort="day",
            metrics="views,estimatedMinutesWatched,averageViewPercentage,likes,subscribersGained",
            filters=f"video=={_video(video_id)}", **_range(days),
        ).execute()
        return _rows(resp)

    @mcp.tool()
    def yt_video_retention(video_id: str, days: int = 90, channel: str = "") -> dict:
        """Curva de retencion de un video: fraccion de audiencia que sigue viendo en cada 5% de su duracion (audienceWatchRatio; >1 = se repite en bucle). `days`: ventana de datos; usa un valor que cubra desde la publicacion."""
        resp = _analytics(channel).reports().query(
            ids="channel==MINE", dimensions="elapsedVideoTimeRatio", sort="elapsedVideoTimeRatio",
            metrics="audienceWatchRatio,relativeRetentionPerformance",
            filters=f"video=={_video(video_id)}", **_range(days),
        ).execute()
        rows = [{k: round(v, 3) for k, v in r.items()} for r in _rows(resp)]
        if not rows:
            return {"video_id": video_id, "samples": [], "note": "sin datos en la ventana"}
        return {
            "video_id": video_id,
            "start": rows[0],
            "end": rows[-1],
            "lowest": min(rows, key=lambda r: r["audienceWatchRatio"]),
            "samples": rows[4::5],
        }

    @mcp.tool()
    def yt_video_audience(by: str = "country", video_id: str = "", days: int = 28, channel: str = "") -> list[dict]:
        """Quien ve el contenido. by: country, deviceType, subscribedStatus, ageGroup o gender (ageGroup y gender devuelven % de espectadores). video_id vacio = todo el canal."""
        allowed = ("country", "deviceType", "subscribedStatus", "ageGroup", "gender")
        if by not in allowed:
            raise ValueError(f"by debe ser uno de: {', '.join(allowed)}")
        demo = by in ("ageGroup", "gender")
        extra = {"filters": f"video=={_video(video_id)}"} if video_id.strip() else {}
        resp = _analytics(channel).reports().query(
            ids="channel==MINE", dimensions=by,
            metrics="viewerPercentage" if demo else "views,estimatedMinutesWatched,averageViewPercentage",
            sort="-viewerPercentage" if demo else "-views", maxResults=15,
            **extra, **_range(days),
        ).execute()
        return _rows(resp)

    return mcp


def authorize(channel: str | None = None):
    from google_auth_oauthlib.flow import InstalledAppFlow

    token_path = _token_path(channel)

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
    # VPS sin navegador: abre un tunel  ssh -L P:localhost:P root@VPS  (P = YT_METRICS_AUTH_PORT) y abre la URL en tu equipo.
    port = int(os.environ.get("YT_METRICS_AUTH_PORT", "8080"))
    creds = flow.run_local_server(port=port, open_browser=False, access_type="offline", prompt="select_account consent")
    with open(token_path, "w", encoding="utf-8") as fh:
        fh.write(creds.to_json())
    os.chmod(token_path, 0o600)
    title = build("youtube", "v3", credentials=creds, cache_discovery=False).channels().list(
        part="snippet", mine=True).execute()["items"][0]["snippet"]["title"]
    print(f"Token guardado en {token_path} (canal: {title})")


if __name__ == "__main__":
    if "--auth" in sys.argv:
        authorize(sys.argv[sys.argv.index("--channel") + 1] if "--channel" in sys.argv else None)
    else:
        build_server().run(transport="streamable-http")
