"""Catalogo de pistas musicales del canal, resuelto por nombre y no por ruta.

Las pistas son licenciadas (Epidemic Sound) y **no se versionan**: viven fuera
del repo. Antes cada build traia clavado ``C:\\Users\\sunse\\Downloads\\ES_...wav``,
asi que ningun script corria en otra maquina. Aca se declara la pista por clave
y se busca el archivo en las carpetas conocidas.

Donde dejar los .wav (en orden de busqueda):
  1. ``$MATHRELAXING_MUSIC_DIR`` (una o varias carpetas separadas por ``os.pathsep``)
  2. ``assets/music/`` dentro del repo (git-ignored)
  3. ``data/music/``
  4. ``~/Music`` y ``~/Downloads``
"""

from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# clave estable -> nombre de archivo tal como lo entrega Epidemic Sound
TRACKS = {
    "betawaves": "ES_Betawaves for Concentration (Short Version) - Joseph Beg.wav",
    "enlightened_drift": "ES_Enlightened Drift - Amber Glow.wav",
    "new_beginning": "ES_A New Beginning (Theta Drone L216Hz R220Hz) - Bruce Brus.wav",
    "how_did_we_get_here": "ES_How Did We Get Here - Hanna Lindgren.wav",
    "pillow_magic": "ES_Pillow Magic - Valante.wav",
}

# Mezcla ambiente estandar de los videos largos (~1555 s en total).
AMBIENT_PLAYLIST = (
    "betawaves",
    "enlightened_drift",
    "new_beginning",
    "how_did_we_get_here",
    "pillow_magic",
)


def search_dirs() -> list[str]:
    dirs: list[str] = []
    env = os.environ.get("MATHRELAXING_MUSIC_DIR", "")
    for d in env.split(os.pathsep):
        if d.strip():
            dirs.append(os.path.expanduser(d.strip()))
    dirs += [
        os.path.join(REPO, "assets", "music"),
        os.path.join(REPO, "data", "music"),
        os.path.expanduser("~/Music"),
        os.path.expanduser("~/Downloads"),
    ]
    return dirs


def _missing(filename: str) -> str:
    listed = "\n".join(f"    - {d}" for d in search_dirs())
    return (
        f"No se encontro la pista '{filename}'.\n"
        f"  Buscada en:\n{listed}\n"
        "  Copiala a assets/music/ o exporta MATHRELAXING_MUSIC_DIR con su carpeta."
    )


def find_track(key_or_path: str, required: bool = True) -> str | None:
    """Ruta a una pista, por clave de `TRACKS`, por nombre de archivo o por ruta.

    Una ruta existente se devuelve tal cual, asi que los `--music` de la linea
    de comandos siguen funcionando sin cambios.
    """
    if not key_or_path:
        if required:
            sys.exit("Falta indicar la pista musical.")
        return None

    if os.path.isabs(key_or_path) or os.sep in key_or_path or "/" in key_or_path:
        if os.path.isfile(key_or_path):
            return key_or_path
        local = os.path.join(REPO, key_or_path)
        if os.path.isfile(local):
            return local

    filename = TRACKS.get(key_or_path, key_or_path)
    for d in search_dirs():
        candidate = os.path.join(d, filename)
        if os.path.isfile(candidate):
            return candidate

    if required:
        sys.exit(_missing(filename))
    return None


def playlist(keys=None, required: bool = True) -> list[str]:
    """Rutas de varias pistas (por defecto, la mezcla ambiente del canal)."""
    out: list[str] = []
    for k in (keys if keys is not None else AMBIENT_PLAYLIST):
        p = find_track(k, required=required)
        if p:
            out.append(p)
    return out
