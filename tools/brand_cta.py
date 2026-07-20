"""Quema el CTA de suscripcion + bug de marca sobre cualquier MP4 terminado.

Los scripts de build son heterogeneos (unos componen overlays PNG, otros no
tienen overlay, otros arman su propio ffmpeg), asi que no hay un unico punto
donde inyectar el CTA en pantalla. Esta herramienta es un **post-proceso
universal**: toma el video final y le quema encima la marca, sin importar como
se construyo.

En Shorts casi nadie lee la descripcion, asi que el CTA en pantalla es el lever
fuerte de conversion (el canal tenia ~29.8k vistas organicas y 45 subs).

    python tools/brand_cta.py -i output/shorts_x/shorts_x.mp4
    python tools/brand_cta.py -i in.mp4 -o out.mp4 --cta "SUBSCRIBE FOR DAILY MATH"
    python tools/brand_cta.py -i in.mp4 --no-handle --cta-start 3 --cta-end 7
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FONT = os.path.join(REPO, "font.ttf")
FALLBACK_FONT = r"C:\Windows\Fonts\segoeuib.ttf"

DEFAULT_CTA = "SUBSCRIBE FOR DAILY MATH"
DEFAULT_HANDLE = "@MathRelaxing"


def _ffprobe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def _esc_path(p: str) -> str:
    """Escapa una ruta de Windows para usarla dentro de un filtro ffmpeg."""
    return p.replace("\\", "/").replace(":", r"\:")


def _esc_text(t: str) -> str:
    return t.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'")


def build_filters(duration: float, *, cta: str, handle: str,
                  cta_start: float, cta_end: float, font: str,
                  cta_y: float = 0.72, handle_y: float = 0.045) -> str:
    f = _esc_path(font)
    parts = []

    if handle:
        parts.append(
            f"drawtext=fontfile='{f}':text='{_esc_text(handle)}'"
            ":fontcolor=white@0.62:fontsize=h/64"
            f":x=(w-text_w)/2:y=h*{handle_y:.3f}"
            ":shadowcolor=black@0.6:shadowx=2:shadowy=2"
        )

    if cta and cta_end > cta_start:
        # Caja oscura detras: las visualizaciones son brillantes y saturadas, el
        # texto plano se pierde. La caja garantiza legibilidad sobre cualquier fondo.
        parts.append(
            f"drawtext=fontfile='{f}':text='{_esc_text(cta)}'"
            ":fontcolor=0xFFE24D:fontsize=h/38"
            f":x=(w-text_w)/2:y=h*{cta_y:.3f}"
            ":box=1:boxcolor=black@0.55:boxborderw=22"
            ":shadowcolor=black@0.8:shadowx=2:shadowy=2"
            f":enable='between(t,{cta_start:.2f},{cta_end:.2f})'"
        )

    return ",".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True)
    ap.add_argument("-o", "--output", default=None,
                    help="Default: <input>_branded.mp4")
    ap.add_argument("--cta", default=DEFAULT_CTA)
    ap.add_argument("--handle", default=DEFAULT_HANDLE)
    ap.add_argument("--no-cta", action="store_true")
    ap.add_argument("--no-handle", action="store_true")
    ap.add_argument("--cta-start", type=float, default=None,
                    help="Segundos (default: 45%% de la duracion)")
    ap.add_argument("--cta-end", type=float, default=None,
                    help="Segundos (default: 85%% de la duracion)")
    ap.add_argument("--cta-y", type=float, default=0.72,
                    help="Posicion vertical del CTA como fraccion de la altura (default 0.72). "
                         "Subir/bajar si choca con overlays propios de la escena.")
    ap.add_argument("--handle-y", type=float, default=0.045,
                    help="Posicion vertical del bug de marca (default 0.045)")
    ap.add_argument("--font", default=None)
    a = ap.parse_args()

    if not os.path.isfile(a.input):
        sys.exit(f"No existe el input: {a.input}")

    font = a.font or (DEFAULT_FONT if os.path.isfile(DEFAULT_FONT) else FALLBACK_FONT)
    if not os.path.isfile(font):
        sys.exit(f"No se encontro una fuente utilizable: {font}")

    dur = _ffprobe_duration(a.input)
    cta_start = a.cta_start if a.cta_start is not None else dur * 0.45
    cta_end = a.cta_end if a.cta_end is not None else dur * 0.85

    out = a.output or os.path.splitext(a.input)[0] + "_branded.mp4"

    vf = build_filters(
        dur,
        cta="" if a.no_cta else a.cta,
        handle="" if a.no_handle else a.handle,
        cta_start=cta_start, cta_end=cta_end, font=font,
        cta_y=a.cta_y, handle_y=a.handle_y,
    )
    if not vf:
        sys.exit("Nada que dibujar (--no-cta y --no-handle a la vez)")

    print(f"[brand_cta] {os.path.basename(a.input)} | {dur:.1f}s | "
          f"CTA {cta_start:.1f}s-{cta_end:.1f}s")

    cmd = [
        "ffmpeg", "-y", "-i", a.input,
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
        "-c:a", "copy",
        out,
    ]
    subprocess.run(cmd, check=True)
    print(f"[brand_cta] LISTO -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
