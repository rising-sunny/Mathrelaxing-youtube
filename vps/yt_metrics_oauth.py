"""Servidor de autorizacion OAuth 2.1 de un solo dueno para el MCP de metricas.

Flujo: el cliente (Claude) se registra solo (DCR), te manda a /approve, tu escribes la
contrasena (MCP_OWNER_PASSWORD) y se emite un access token (1 h) + refresh token (30 d, rota).
Los tokens se guardan hasheados (sha256) en un JSON con permisos 0600.
"""
import hashlib
import hmac
import html
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mcp.server.auth.provider import (
    AccessToken, AuthorizationCode, AuthorizationParams, RefreshToken,
    RegistrationError, TokenError, construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

SCOPE = "metrics"
ACCESS_TTL, REFRESH_TTL, CODE_TTL, PENDING_TTL = 3600, 30 * 86400, 300, 600
MAX_CLIENTS, MAX_FAILS = 200, 5


def _h(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class OwnerOAuthProvider:
    def __init__(self, store_path: str, issuer: str):
        self.path, self.issuer = Path(store_path), issuer.rstrip("/")
        self.db = json.loads(self.path.read_text()) if self.path.exists() else {}
        for key in ("clients", "access", "refresh"):
            self.db.setdefault(key, {})
        self.codes: dict[str, AuthorizationCode] = {}
        self.pending: dict[str, tuple] = {}
        self.fails: list[float] = []

    def _save(self) -> None:
        now = time.time()
        for kind in ("access", "refresh"):
            self.db[kind] = {k: v for k, v in self.db[kind].items() if v["expires_at"] > now}
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(self.db, fh)
        os.replace(tmp, self.path)

    # --- clientes (registro dinamico) ---
    async def get_client(self, client_id: str):
        data = self.db["clients"].get(client_id)
        return OAuthClientInformationFull.model_validate(data) if data else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if len(self.db["clients"]) >= MAX_CLIENTS:
            raise RegistrationError(error="invalid_client_metadata", error_description="too many clients")
        self.db["clients"][client_info.client_id] = client_info.model_dump(mode="json")
        self._save()

    # --- autorizacion: la pantalla /approve pide la contrasena del dueno ---
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        now = time.time()
        self.pending = {k: v for k, v in self.pending.items() if v[2] > now}
        rid = secrets.token_urlsafe(24)
        self.pending[rid] = (client, params, now + PENDING_TTL)
        return f"{self.issuer}/approve?rid={rid}"

    def approve(self, rid: str) -> str | None:
        """Emite el codigo para una peticion pendiente y devuelve la URL de redireccion."""
        entry = self.pending.pop(rid, None)
        if not entry or entry[2] < time.time():
            return None
        client, params, _ = entry
        code = secrets.token_urlsafe(32)
        self.codes[code] = AuthorizationCode(
            code=code, scopes=params.scopes or [SCOPE], expires_at=time.time() + CODE_TTL,
            client_id=client.client_id, code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(self, client, authorization_code: str):
        code = self.codes.get(authorization_code)
        ok = code and code.client_id == client.client_id and code.expires_at > time.time()
        return code if ok else None

    async def exchange_authorization_code(self, client, authorization_code) -> OAuthToken:
        self.codes.pop(authorization_code.code, None)
        return self._issue(client.client_id, authorization_code.scopes, authorization_code.resource)

    # --- tokens ---
    def _issue(self, client_id: str, scopes: list[str], resource: str | None) -> OAuthToken:
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = int(time.time())
        base = {"client_id": client_id, "scopes": scopes, "resource": resource}
        self.db["access"][_h(access)] = {**base, "expires_at": now + ACCESS_TTL, "pair": _h(refresh)}
        self.db["refresh"][_h(refresh)] = {**base, "expires_at": now + REFRESH_TTL, "pair": _h(access)}
        self._save()
        return OAuthToken(access_token=access, token_type="Bearer", expires_in=ACCESS_TTL,
                          scope=" ".join(scopes), refresh_token=refresh)

    async def load_access_token(self, token: str):
        rec = self.db["access"].get(_h(token))
        if not rec or rec["expires_at"] <= time.time():
            return None
        return AccessToken(token=token, client_id=rec["client_id"], scopes=rec["scopes"],
                           expires_at=rec["expires_at"], resource=rec["resource"])

    async def load_refresh_token(self, client, refresh_token: str):
        rec = self.db["refresh"].get(_h(refresh_token))
        if not rec or rec["client_id"] != client.client_id or rec["expires_at"] <= time.time():
            return None
        return RefreshToken(token=refresh_token, client_id=rec["client_id"], scopes=rec["scopes"],
                            expires_at=rec["expires_at"], resource=rec["resource"])

    async def exchange_refresh_token(self, client, refresh_token, scopes: list[str]) -> OAuthToken:
        if scopes and not set(scopes) <= set(refresh_token.scopes):
            raise TokenError(error="invalid_scope", error_description="scope not granted")
        await self.revoke_token(refresh_token)
        return self._issue(client.client_id, scopes or refresh_token.scopes, refresh_token.resource)

    async def revoke_token(self, token) -> None:
        h = _h(token.token)
        for kind in ("access", "refresh"):
            rec = self.db[kind].pop(h, None)
            if rec:
                other = "refresh" if kind == "access" else "access"
                self.db[other].pop(rec["pair"], None)
        self._save()


def register_approval_routes(mcp, provider: OwnerOAuthProvider, owner_password: str) -> None:
    def page(rid: str, client, error: str = "", status: int = 200) -> HTMLResponse:
        name = html.escape(client.client_name or client.client_id)
        dest = html.escape(urlparse(str(client.redirect_uris[0])).netloc)
        err = f"<p style='color:#b00'>{html.escape(error)}</p>" if error else ""
        return HTMLResponse(
            f"<!doctype html><meta name=viewport content='width=device-width'>"
            f"<title>Autorizar</title><body style='font-family:sans-serif;max-width:26rem;margin:3rem auto;padding:0 1rem'>"
            f"<h2>MathRelaxing · métricas</h2><p><b>{name}</b> ({dest}) pide acceso de solo lectura "
            f"a las métricas del canal.</p>{err}<form method=post>"
            f"<input type=hidden name=rid value='{html.escape(rid)}'>"
            f"<input type=password name=password placeholder='Contraseña' autofocus required "
            f"style='width:100%;padding:.6rem;margin:.5rem 0'>"
            f"<button style='padding:.6rem 1.2rem'>Autorizar</button></form>", status_code=status)

    @mcp.custom_route("/approve", methods=["GET", "POST"])
    async def approve(request: Request) -> Response:
        if request.method == "GET":
            rid = request.query_params.get("rid", "")
        else:
            form = parse_qs((await request.body()).decode(), keep_blank_values=True)
            rid = form.get("rid", [""])[0]
            password = form.get("password", [""])[0]
        entry = provider.pending.get(rid)
        if not entry or entry[2] < time.time():
            return HTMLResponse("Solicitud expirada. Vuelve a conectar desde Claude.", status_code=400)
        if request.method == "GET":
            return page(rid, entry[0])
        now = time.time()
        provider.fails = [t for t in provider.fails if now - t < 600]
        if len(provider.fails) >= MAX_FAILS:
            return HTMLResponse("Demasiados intentos. Espera 10 minutos.", status_code=429)
        if not hmac.compare_digest(password.encode(), owner_password.encode()):
            provider.fails.append(now)
            return page(rid, entry[0], "Contraseña incorrecta", 401)
        return RedirectResponse(provider.approve(rid), status_code=303)
