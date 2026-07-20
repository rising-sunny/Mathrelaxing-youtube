"""Guard de deprecacion para el formato de 1 hora ("Deep Focus").

Los videos de 1 hora rinden ~9 vistas de promedio (0% pasan las 100), mientras
consumen el render mas caro del pipeline (GPU en Vast.ai). Los shorts de 13-20s
promedian ~444 vistas con el 70% pasando las 100.

El codigo queda intacto: solo se pide confirmacion explicita para no quemar
presupuesto de render por accidente.

    python build_aizawa_1h.py            -> bloqueado, explica por que
    python build_aizawa_1h.py --force    -> corre igual
    MATHRELAXING_ALLOW_1H=1 python ...   -> corre igual
"""

from __future__ import annotations

import os
import sys

_BANNER = """
==============================================================
  FORMATO DEPRECADO: video de 1 hora ("Deep Focus")
==============================================================
  Datos del canal (jul 2026):
    - 1 hora : ~9 vistas de promedio, 0% pasa las 100
    - shorts : ~444 de promedio, 70% pasa las 100 (13-20s)

  Este render es el mas caro del pipeline y el formato no tiene
  traccion. Invertir en shorts de 13-20s (cimatica / ondas /
  fractales / atractores) rinde mucho mas.

  Si igual queres continuar:
    python {script} --force
==============================================================
"""


def guard_1h_format(script_path: str | None = None) -> None:
    """Aborta salvo que se pase --force o MATHRELAXING_ALLOW_1H=1."""
    if "--force" in sys.argv or os.environ.get("MATHRELAXING_ALLOW_1H") == "1":
        print("[deprecado] formato de 1 hora: continuando por --force")
        return
    script = os.path.basename(script_path or (sys.argv[0] or "build_*_1h.py"))
    print(_BANNER.format(script=script))
    sys.exit(1)
