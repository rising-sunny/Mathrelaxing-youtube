"""Rutas del repo resueltas en runtime (cero rutas absolutas de una maquina).

Motivo: media docena de scripts traia clavada la ruta del PC original
(``C:\\dev\\MathRelaxing-videos-music``, ``C:\\Windows\\Fonts\\segoeui.ttf``,
carpetas de scratch de otra herramienta), asi que solo corrian ahi. Todo lo que
dependa del disco se pide a este modulo.

Overrides por entorno:
  MATHRELAXING_BLENDER   ruta al ejecutable de Blender
  MATHRELAXING_FONT      tipografia por defecto para overlays
"""

from __future__ import annotations

import glob
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(REPO, "output")
DATA = os.path.join(REPO, "data")
SCENES = os.path.join(REPO, "scenes")
THUMBNAILS = os.path.join(OUTPUT, "thumbnails")
REPO_FONT = os.path.join(REPO, "font.ttf")


def output_dir(name: str, create: bool = True) -> str:
    """``output/<name>/`` — carpeta de trabajo de un video."""
    d = os.path.join(OUTPUT, name)
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def frames_dir(name: str, create: bool = False) -> str:
    d = os.path.join(OUTPUT, name, "frames")
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def thumbnail_path(filename: str, create: bool = True) -> str:
    """``output/thumbnails/<filename>`` — las miniaturas viven en el repo."""
    if create:
        os.makedirs(THUMBNAILS, exist_ok=True)
    return os.path.join(THUMBNAILS, filename)


def events_path(name: str) -> str:
    return os.path.join(DATA, f"{name}_events.json")


def find_blender(required: bool = True) -> str | None:
    """Blender portable de ``tools/blender/``, el del PATH, o el del entorno."""
    env = os.environ.get("MATHRELAXING_BLENDER")
    if env and os.path.isfile(env):
        return env

    for pattern in ("blender.exe", "blender"):
        hits = sorted(glob.glob(os.path.join(REPO, "tools", "blender", "**", pattern),
                                recursive=True))
        hits = [h for h in hits if os.path.isfile(h)]
        if hits:
            return hits[0]

    which = shutil.which("blender")
    if which:
        return which

    if required:
        sys.exit(
            "No se encontro Blender.\n"
            "  - instalalo portable en tools/blender/, o\n"
            "  - dejalo en el PATH, o\n"
            "  - exporta MATHRELAXING_BLENDER con la ruta al ejecutable."
        )
    return None


# Candidatos por estilo, en orden de preferencia (Windows → macOS → Linux).
_FONT_CANDIDATES = {
    "bold": ("segoeuib.ttf", "arialbd.ttf", "Helvetica.ttc",
             "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "NotoSans-Bold.ttf"),
    "regular": ("segoeui.ttf", "arial.ttf", "Helvetica.ttc",
                "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "NotoSans-Regular.ttf"),
    "math": ("cambria.ttc", "constan.ttf", "times.ttf", "Times New Roman.ttf",
             "DejaVuSerif.ttf", "LiberationSerif-Regular.ttf", "NotoSerif-Regular.ttf"),
}

_FONT_DIRS = (
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    "/Library/Fonts",
    "/System/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/.local/share/fonts"),
)

_font_cache: dict[str, str] = {}


def font_path(style: str = "regular") -> str:
    """Ruta a una tipografia utilizable para overlays.

    Busca el estilo pedido en las carpetas de fuentes del sistema; si no hay
    nada, cae al ``font.ttf`` que viaja en el repo. Devuelve "" solo si no
    existe ninguna (el llamador usa entonces la fuente por defecto de PIL).
    """
    if style in _font_cache:
        return _font_cache[style]

    env = os.environ.get("MATHRELAXING_FONT")
    if env and os.path.isfile(env):
        _font_cache[style] = env
        return env

    for name in _FONT_CANDIDATES.get(style, _FONT_CANDIDATES["regular"]):
        for d in _FONT_DIRS:
            if not os.path.isdir(d):
                continue
            direct = os.path.join(d, name)
            if os.path.isfile(direct):
                _font_cache[style] = direct
                return direct
            hits = glob.glob(os.path.join(d, "**", name), recursive=True)
            if hits:
                _font_cache[style] = hits[0]
                return hits[0]

    found = REPO_FONT if os.path.isfile(REPO_FONT) else ""
    _font_cache[style] = found
    return found
