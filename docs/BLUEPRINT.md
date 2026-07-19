# Blueprint del Proyecto: Ecosistema Audiovisual Procedimental (Matemáticas y Física)

## 1. Visión General del Proyecto
El objetivo es construir un sistema cien por ciento automatizado ("headless" y "Zero GUI") para generar videos de larga duración (3+ horas) destinados a YouTube (canal @MathRelaxing). Los videos consisten en evoluciones procedimentales de fenómenos físicos (ej. dilatación del tiempo, campos vectoriales). Toda la orquestación, desde el diseño de la geometría hasta el ensamblaje final, nace a partir de instrucciones en lenguaje natural dadas a una IA agéntica, la cual se encarga de traducirlas a código y scripts, eliminando la manipulación manual de interfaces.

## 2. Arquitectura de la Infraestructura (Híbrida: Local/Nube)
*   **Torre de Control (Orquestación Local):** Equipo local (procesador i9, 32GB RAM) ejecutando el entorno Windsurf IDE, CLI de Gemini y el servidor MCP. Se encarga exclusivamente de la dirección inteligente: generar los scripts de Blender, gestionar el audio y hacer previsualizaciones rápidas en baja resolución.
*   **Motor Gráfico Cero-Interfaz:** Blender controlado de forma estricta mediante su API interna de Python (`bpy`). Nunca se abre la interfaz gráfica tradicional.
*   **Servidor de Renderizado (Nube):** Instancia activa en Vast.ai con GPU dedicada para asumir toda la carga de renderizado fotorrealista continuo.
*   **Generación de Texturas:** Modelo Flux Dev alojado de manera paralela en la instancia de Vast.ai.
*   **Procesamiento de Audio y Ensamblaje:** Generadores de audio integrados por consola para fondos épicos y sonificación de datos (metales/shofar), multiplexados finalmente vía FFmpeg.

## 3. Reglas Centrales de Generación
1.  **Flexibilidad de Prompts (Input Dinámico):** El agente MCP debe tener la capacidad de construir el ecosistema visual a través de dos vías: aplicando ecuaciones matemáticas exactas proporcionadas por el usuario, o bien, deduciendo e inyectando las fórmulas correspondientes a partir de una descripción teórica (ej. "simula el comportamiento de un atractor caótico").
2.  **Evolución Continua (Cero Loops):** Las variables espaciales y físicas deben mutar progresivamente desde el minuto 0 hasta la hora final del video.
3.  **Sonificación Directa (Data-Driven Audio):** Los eventos clave de la geometría dictan los estímulos sonoros. Las curvas matemáticas exportan datos para disparar efectos de impacto lento en sincronía absoluta.
4.  **Armonía Tonal y Ducking:** Base de audio ambiental épica fijada a una tonalidad exacta (ej. Do menor), aplicando reducción de volumen automatizada (Sidechain) cuando las frecuencias graves de los eventos matemáticos entren en escena.

## 4. Referencias Estéticas y de Ritmo (Moodboard)
*   **Benchmark Visual Procedimental (Julius Horsthuis):** Exploración de física y matemáticas a través de cámara lenta, inmersiva, generando entornos oscuros y majestuosos.
*   **Benchmark de Diseño Sonoro (Melodysheep):** Referencia absoluta para el "Cinematic Drone" y el "shofar cósmico". Reverberaciones infinitas, ataque acústico muy lento y ausencia de ruido electrónico estridente.
*   **Benchmark de Fusión Teórico-Estética (Interstellar / Kip Thorne):** El estándar para que la deformación visual de la geometría nazca estrictamente de la inyección de leyes físicas reales en los nodos.

## 5. Flujo de Trabajo Agéntico (Fases de Implementación)
*   **Fase 1: Instrucción y Arquitectura (Local):** El usuario entrega la premisa teórica o ecuación. El agente formula el script completo en Python (`bpy`) que construirá los nodos, las luces y la matemática de audio.
*   **Fase 2: Piloto Silencioso (Local):** El agente ejecuta de fondo el script en la PC local de forma momentánea, renderizando únicamente un fotograma de prueba rápida (o clip de 3 segundos en calidad mínima) para validación del director.
*   **Fase 3: Despliegue en la Nube:** Tras recibir la aprobación humana en el chat, el agente empaqueta los scripts y envía la tarea de forma autónoma al servidor remoto de Vast.ai.
*   **Fase 4: Ejecución Masiva (Nube):** La instancia en la nube ejecuta el archivo en segundo plano, solicita materiales dinámicos a Flux Dev, genera las pistas de síntesis cósmica, renderiza el 3D y consolida todo con FFmpeg.