# MathRelaxing — Ecosistema Audiovisual Procedimental

Sistema **headless** ("Zero GUI") para generar videos de fenómenos
matemáticos/físicos para YouTube ([@MathRelaxing](https://www.youtube.com/@MathRelaxing)):
hoy, shorts verticales de 13-20 s. Toda la generación nace de instrucciones en
lenguaje natural, traducidas a escenas procedurales (rasterizado `numpy` o `bpy`
de Blender), síntesis de audio y ensamblaje con FFmpeg.

Documento de diseño original: [docs/BLUEPRINT.md](docs/BLUEPRINT.md)
(**histórico**: describe la ambición inicial —videos de 3 h, render
fotorrealista en la nube, texturas con Flux Dev—. El pipeline pivoteó a
shorts con motor `numpy` local; este README manda sobre el blueprint).

## Arquitectura (resumen)

- **Orquestación local** (i9-10900 / 32 GB): genera scripts y previews en baja
  resolución. Sin GPU NVIDIA local → los previews van por **Eevee** o CPU.
- **Motor gráfico**: rasterizado `numpy`/PIL para la mayoría de los shorts, y
  Blender 4.4 vía `bpy` (siempre `--background`, nunca GUI) para las escenas 3D.
- **Render en la nube**: **Vast.ai** vía `tools/cloud_render.py`, reservado a lo
  que no rinde en local (hoy casi nada: los shorts salen en minutos con `numpy`).
- **Audio**: síntesis procedural + sonificación dirigida por datos, mux con FFmpeg
  (drone en tonalidad fija + *sidechain/ducking*).

## Estructura

| Carpeta    | Contenido                                                        |
|------------|------------------------------------------------------------------|
| `scenes/`  | Escenas procedurales (`numpy` o `bpy`)                           |
| `audio/`   | Síntesis del drone + sonificación dirigida por datos             |
| `render/`  | Configs de render y despliegue a Vast.ai                         |
| `data/`    | Eventos de geometría exportados (JSON) para sonificación         |
| `output/`  | Frames/clips renderizados (git-ignored)                          |
| `tools/`   | Utilidades compartidas (+ Blender portable en `tools/blender/`, git-ignored) |
| `assets/`  | Pistas musicales licenciadas (git-ignored)                       |
| `docs/`    | Diseño y documentación                                           |

## Estado

**En producción.** 78 videos publicados y ~28 escenas en `scenes/`. El pipeline
opera de punta a punta: escena → frames → audio → mux → overlay/CTA → subida.

El foco actual son los **shorts verticales de 13-20 s** (ver *Formato de 1 hora*
más abajo), renderizados con el motor `numpy` local; el camino `bpy` + nube queda
para lo que lo necesite.

Dos motores conviven en `scenes/`:

| Motor | Cómo se invoca | Escenas |
|---|---|---|
| `numpy` | rasterizado puro en Python/PIL, sin Blender | Mandelbrot, Julia, solitones, cimática espectral, Clifford, Thomas, Hopf, three-body, reacción-difusión, Aizawa, Lorenz, pila de arena abeliana, 600-cell 4D, espiral de primos, teselado hiperbólico, árbol de otoño, aurora boreal, bola peluda, lluvia en el vidrio, Buddhabrot |
| `eevee` | Blender headless (`--background`) | ABC flow, curl, péndulo doble, gravedad, Chladni, Rössler, tokamak, slice |

`render/build_clip.py` es el orquestador genérico; cada `build_*.py` de la raíz
es un preset que lo llama con sus parámetros.

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

## Formato de 1 hora — deprecado

Los `build_*_1h.py` están **deprecados** y piden `--force` para correr
(`_deprecated_1h.py`). Datos del canal (jul 2026):

| Formato | Vistas promedio | % sobre 100 vistas |
|---|---|---|
| 1 hora "Deep Focus" | ~9 | 0% |
| Shorts 13-20s | ~444 | 70% |

Es el render más caro del pipeline (GPU en Vast.ai) sobre el formato con menos
tracción. El código queda intacto; el guard solo evita quemar presupuesto por
accidente. **Perfil de short ideal:** 13-20s, familias cimática / ondas /
fractales / atractores, título con número grande explícito.

## Decisiones abiertas

- **Motor de render para finales (Eevee vs Cycles vs híbrido):** se decide con un
  A/B sobre un frame real renderizado en Vast.ai, comparando costo/look. Hasta
  entonces, Eevee para todo el preview local.

## Configuración local (nada de rutas absolutas)

Los scripts resuelven todo en runtime desde el repo. Lo que vive fuera del repo
se busca en varias carpetas y se puede fijar por variable de entorno:

| Variable | Qué controla | Fallback |
|---|---|---|
| `MATHRELAXING_MUSIC_DIR` | Carpeta(s) con las pistas `.wav` licenciadas | `assets/music/`, `data/music/`, `~/Music`, `~/Downloads` |
| `MATHRELAXING_BLENDER` | Ejecutable de Blender | `tools/blender/**`, luego el del `PATH` |
| `MATHRELAXING_FONT` | Tipografía de los overlays | fuentes del sistema, luego `font.ttf` del repo |
| `MATHRELAXING_ENV_FILE` | `.env` con credenciales de Vast.ai | `.env` del repo, `~/.mathrelaxing.env` |

- `tools/paths.py` — rutas del repo, descubrimiento de Blender y de tipografías.
- `tools/music_library.py` — catálogo de pistas por clave (`betawaves`,
  `enlightened_drift`, `new_beginning`, `how_did_we_get_here`, `pillow_magic`).
  Los builds piden la clave; el archivo puede estar donde sea. `--music`/`--audio`
  también aceptan una ruta directa.

Las miniaturas se escriben en `output/thumbnails/`.

## Requisitos locales

- **Blender 4.4.3 portable** en `tools/blender/` — solo para las escenas `bpy`;
  las escenas `numpy` no lo necesitan.
- **FFmpeg 7.x** en el PATH.
- **Python 3.x** para orquestación. El scripting `bpy` usa el Python *embebido* de Blender,
  no el del sistema.
