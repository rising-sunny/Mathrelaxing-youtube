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

# Dos canales con marcas distintas. Sin esto, una pieza de ambiente publicada
# en el canal chico se lleva el CTA, la tienda y los tags de matemática del
# canal grande, que ahí no describen el contenido y ensucian las señales.
# sub_confirmation=1 abre el diálogo de suscripción al hacer click.
CHANNELS = {
    "mathrelaxing": {
        "name": "MathRelaxing",
        "handle": "@MathRelaxing",
        "subscribe_url": "https://www.youtube.com/@MathRelaxing?sub_confirmation=1",
        "store_url": "https://mathrelaxing.store",
        "subscribe_cta": "🔔 New math visualization every day — subscribe: "
                         "https://www.youtube.com/@MathRelaxing?sub_confirmation=1",
        "store_cta": "✨ Math-inspired designs at our store: https://mathrelaxing.store",
        "base_tags": [
            "math", "physics", "mathrelaxing", "satisfying", "oddly satisfying",
            "generative art", "simulation", "science", "visuals", "python",
        ],
        "base_hashtags": ["#MathRelaxing", "#math", "#satisfying"],
    },
    "nostalgicmood": {
        "name": "Nostalgic Mood",
        "handle": "@TheNostalgicMood",
        "subscribe_url": "https://www.youtube.com/@TheNostalgicMood?sub_confirmation=1",
        "store_url": None,
        "subscribe_cta": "🔔 More generated worlds like this — subscribe: "
                         "https://www.youtube.com/@TheNostalgicMood?sub_confirmation=1",
        "store_cta": None,
        "base_tags": [
            "generative art", "procedural art", "creative coding", "relaxing",
            "ambient", "cozy", "aesthetic", "satisfying", "visuals", "python",
        ],
        "base_hashtags": ["#NostalgicMood", "#generativeart", "#cozy"],
    },
}

DEFAULT_CHANNEL = "mathrelaxing"


def channel(name: str | None = None) -> dict:
    key = (name or DEFAULT_CHANNEL).strip().lower().replace(" ", "").replace("@", "")
    if key not in CHANNELS:
        raise KeyError(f"Canal desconocido: {name!r}. Conocidos: {sorted(CHANNELS)}")
    return CHANNELS[key]


# Alias del canal por defecto, para no romper los scripts que ya los importan.
_D = CHANNELS[DEFAULT_CHANNEL]
CHANNEL_HANDLE = _D["handle"]
SUBSCRIBE_URL = _D["subscribe_url"]
STORE_URL = _D["store_url"]
SUBSCRIBE_CTA = _D["subscribe_cta"]
STORE_CTA = _D["store_cta"]
BASE_TAGS = _D["base_tags"]
BASE_HASHTAGS = _D["base_hashtags"]

# Señales de que la descripción ya pide la suscripción (evita duplicar).
_SUBSCRIBE_MARKERS = ("subscribe", "suscrib", "sub_confirmation")


def has_subscribe_cta(description: str) -> bool:
    low = (description or "").lower()
    return any(m in low for m in _SUBSCRIBE_MARKERS)


def ensure_subscribe_cta(description: str, channel_name: str | None = None) -> str:
    """Devuelve la descripción garantizando un CTA de suscripción al inicio.

    Idempotente: si ya pide la suscripción, la deja intacta.
    """
    desc = (description or "").strip()
    if has_subscribe_cta(desc):
        return desc
    cta = channel(channel_name)["subscribe_cta"]
    return f"{cta}\n\n{desc}" if desc else cta


def build_description(
    body: str,
    *,
    hashtags: list[str] | None = None,
    subscribe: bool = False,   # el CTA de suscripcion ya no va en la descripcion
    store: bool = False,   # la linea de la tienda ya no va en las descripciones
    channel_name: str | None = None,
) -> str:
    """Arma una descripción completa: CTA de suscripción → cuerpo → tienda → hashtags."""
    ch = channel(channel_name)
    parts: list[str] = []
    if subscribe:
        parts.append(ch["subscribe_cta"])
    body = (body or "").strip()
    if body:
        parts.append(body)
    if store and ch["store_cta"]:
        parts.append(ch["store_cta"])
    tags = list(ch["base_hashtags"])
    for h in hashtags or []:
        h = h if h.startswith("#") else f"#{h}"
        if h.lower() not in {t.lower() for t in tags}:
            tags.append(h)
    parts.append(" ".join(tags))
    text = "\n\n".join(parts)
    # YouTube rechaza < y > en el cuadro de descripcion: si se cuelan (tipico
    # al escribir "Re(s) > 1"), el formulario falla al pegar y no dice por que.
    bad = {c for c in "<>" if c in text}
    if bad:
        raise ValueError(
            f"La descripcion tiene {' y '.join(sorted(bad))}: YouTube no los "
            "acepta. Escribelo en palabras o usa la relacion al reves.")
    return text


def build_tags(extra: list[str] | None = None, limit: int = 30,
               channel_name: str | None = None) -> list[str]:
    """Tags base del canal + específicas del video, sin duplicados."""
    out: list[str] = []
    seen: set[str] = set()
    for t in list(channel(channel_name)["base_tags"]) + list(extra or []):
        t = str(t).strip().lstrip("#")
        k = t.lower()
        if t and k not in seen:
            seen.add(k)
            out.append(t)
        if len(out) >= limit:
            break
    return out
