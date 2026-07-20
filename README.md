# MathRelaxing — Ecosistema Audiovisual Procedimental

Sistema **headless** ("Zero GUI") para generar videos largos (3 h+) de fenómenos
matemáticos/físicos para YouTube ([@MathRelaxing](https://www.youtube.com/@MathRelaxing)).
Toda la generación nace de instrucciones en lenguaje natural, traducidas a scripts
`bpy` (Blender), síntesis de audio procedural y ensamblaje con FFmpeg.

Documento de diseño completo: [docs/BLUEPRINT.md](docs/BLUEPRINT.md).

## Arquitectura (resumen)

- **Orquestación local** (i9-10900 / 32 GB): genera scripts y previews en baja
  resolución. Sin GPU NVIDIA local → los previews van por **Eevee** o CPU.
- **Motor gráfico**: Blender 4.4 vía `bpy`, siempre `--background` (nunca GUI).
- **Render final**: nube en **Vast.ai** (GPU dedicada, paralelizable por rangos de frames).
- **Texturas**: Flux Dev como *pre-pase* (no concurrente con el render, por VRAM).
- **Audio**: síntesis procedural + sonificación dirigida por datos, mux con FFmpeg
  (drone en tonalidad fija + *sidechain/ducking*).

## Estructura

| Carpeta    | Contenido                                                        |
|------------|------------------------------------------------------------------|
| `scenes/`  | Scripts `bpy` de escenas procedurales                            |
| `audio/`   | Síntesis del drone + sonificación dirigida por datos             |
| `render/`  | Configs de render y despliegue a Vast.ai                         |
| `data/`    | Eventos de geometría exportados (JSON) para sonificación         |
| `output/`  | Frames/clips renderizados (git-ignored)                          |
| `tools/`   | Blender portable y utilidades locales (git-ignored)              |
| `docs/`    | Diseño y documentación                                           |

## Estado

🚧 **Bootstrap.** Primer objetivo: un *vertical slice* de 3 s que pruebe la cadena
completa de punta a punta antes de gastar en la nube:

1. Escena paramétrica `bpy` nacida de una ecuación.
2. Evolución continua de un parámetro sobre ~72 frames (3 s @ 24 fps), sin loop.
3. Export de eventos de geometría a JSON (base de la sonificación).
4. Render local headless en baja resolución (Eevee).
5. Drone *placeholder* en Do menor + *mux* con FFmpeg (con *sidechain*).

## Conversión a suscriptor (CTA) — leer antes de publicar

**Contexto (2026-07):** el canal tenía ~29.8k vistas orgánicas y solo **45
suscriptores**. Auditoría: **0 de 16** `upload_*.py` pedían la suscripción y el
overlay tampoco, mientras **16 de 16** linkeaban la tienda. Había CTA de tienda
en todos lados y CTA de suscripción en ninguno.

El CTA vive en tres capas:

| Capa | Archivo | Cobertura |
|---|---|---|
| Descripción | `tools/metadata.py` + `tools/youtube_uploader.py` | **Automática en toda subida** — `upload_video_to_youtube` antepone el CTA si falta (idempotente) |
| En pantalla (overlay PNG) | `tools/short_text_overlay.py` | Solo la ruta de `build_clifford_short.py` (sin re-encode) |
| En pantalla (post-proceso) | `tools/brand_cta.py` | **Cualquier MP4 terminado** — usar en los builds que no pasan por `short_text_overlay` |

```bat
:: agregar CTA + marca a un video ya construido (re-encodea)
python tools/brand_cta.py -i output/shorts_x/shorts_x.mp4
```

No apliques `brand_cta.py` a la salida de `build_clifford_short.py`: esa ruta ya
trae el CTA quemado en el overlay y quedaría duplicado.

**Backfill del catálogo:** `tools/backfill_subscribe_cta.py` agrega el CTA a las
descripciones ya publicadas (idempotente, preserva título/tags/categoría).
Ejecutado el 2026-07-19 → **78/78 videos** piden la suscripción.

## Decisiones abiertas

- **Motor de render para finales (Eevee vs Cycles vs híbrido):** se decide con un
  A/B sobre un frame real renderizado en Vast.ai, comparando costo/look. Hasta
  entonces, Eevee para todo el preview local.

## Requisitos locales

- **Blender 4.4.3 portable** en `tools/blender/` (descarga gestionada por el repo).
- **FFmpeg 7.x** en el PATH.
- **Python 3.x** para orquestación. El scripting `bpy` usa el Python *embebido* de Blender,
  no el del sistema.
