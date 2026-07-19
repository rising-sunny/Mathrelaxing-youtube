"""Metadata compartida para uploads de MathRelaxing.

Motivo (2026-07): el canal tenía ~29.8k vistas orgánicas y solo 45 suscriptores.
Auditoría del repo: **0 de 16** `upload_*.py` pedían la suscripción, **16 de 16**
linkeaban la tienda, y el overlay en pantalla tampoco la pedía. Había CTA de
tienda en todos lados y CTA de suscripción en ninguno.

Este módulo centraliza la metadata para que **el pedido de suscripción vaya
siempre**. `ensure_subscribe_cta()` la usa el uploader para garantizarlo incluso
en los scripts viejos que arman la descripción a mano.
"""

from __future__ import annotations

CHANNEL_HANDLE = "@MathRelaxing"
# sub_confirmation=1 abre el diálogo de suscripción al hacer click.
SUBSCRIBE_URL = "https://www.youtube.com/@MathRelaxing?sub_confirmation=1"
STORE_URL = "https://mathrelaxing.store"

SUBSCRIBE_CTA = f"🔔 New math visualization every day — subscribe: {SUBSCRIBE_URL}"
STORE_CTA = f"✨ Math-inspired designs at our store: {STORE_URL}"

BASE_TAGS = [
    "math", "physics", "mathrelaxing", "satisfying", "oddly satisfying",
    "generative art", "simulation", "science", "visuals", "python",
]

BASE_HASHTAGS = ["#MathRelaxing", "#math", "#satisfying"]

# Señales de que la descripción ya pide la suscripción (evita duplicar).
_SUBSCRIBE_MARKERS = ("subscribe", "suscrib", "sub_confirmation")


def has_subscribe_cta(description: str) -> bool:
    low = (description or "").lower()
    return any(m in low for m in _SUBSCRIBE_MARKERS)


def ensure_subscribe_cta(description: str) -> str:
    """Devuelve la descripción garantizando un CTA de suscripción al inicio.

    Idempotente: si ya pide la suscripción, la deja intacta.
    """
    desc = (description or "").strip()
    if has_subscribe_cta(desc):
        return desc
    return f"{SUBSCRIBE_CTA}\n\n{desc}" if desc else SUBSCRIBE_CTA


def build_description(
    body: str,
    *,
    hashtags: list[str] | None = None,
    subscribe: bool = True,
    store: bool = True,
) -> str:
    """Arma una descripción completa: CTA de suscripción → cuerpo → tienda → hashtags."""
    parts: list[str] = []
    if subscribe:
        parts.append(SUBSCRIBE_CTA)
    body = (body or "").strip()
    if body:
        parts.append(body)
    if store:
        parts.append(STORE_CTA)
    tags = list(BASE_HASHTAGS)
    for h in hashtags or []:
        h = h if h.startswith("#") else f"#{h}"
        if h.lower() not in {t.lower() for t in tags}:
            tags.append(h)
    parts.append(" ".join(tags))
    return "\n\n".join(parts)


def build_tags(extra: list[str] | None = None, limit: int = 30) -> list[str]:
    """Tags base del canal + específicas del video, sin duplicados."""
    out: list[str] = []
    seen: set[str] = set()
    for t in list(BASE_TAGS) + list(extra or []):
        t = str(t).strip().lstrip("#")
        k = t.lower()
        if t and k not in seen:
            seen.add(k)
            out.append(t)
        if len(out) >= limit:
            break
    return out
