"""Piezas ambientales generativas. Loop exacto por construccion.

El drone generico del repo son cinco senoidales fijas sobre un Do menor: sirve
de colchon debajo de los golpes de una simulacion, pero no es una composicion.
Cuando la musica es contenido y no acompanamiento, se escribe entera.

Todo es PERIODICO EN T por construccion, asi que el loop no necesita crossfade:

  - cada frecuencia se ajusta al multiplo mas cercano de 1/T, lo que a 15 s
    desafina como mucho 0.033 Hz (inaudible) y garantiza ciclo entero;
  - los LFO usan multiplos enteros de 1/T;
  - las campanas se suman con envoltura circular, asi que la cola de la ultima
    reaparece al principio;
  - el viento se sintetiza en el dominio de la frecuencia (fase aleatoria sobre
    magnitudes moldeadas), que es periodico por definicion;
  - la reverb es convolucion CIRCULAR via FFT, que conserva la periodicidad.

Cada pieza es un preset: acorde del pad, bajo, escala de las campanas y mezcla.
Las escalas son pentatonicas, que al no tener semitonos no pueden chocar contra
el pad por mas que las campanas caigan en cualquier orden.

    python audio/ambient_score.py --preset autumn --outdir output/shorts_autumn --duration 15
    python audio/ambient_score.py --preset aurora --outdir output/shorts_aurora --duration 15
"""

from __future__ import annotations

import argparse
import os
import wave

import numpy as np

SR = 48000

PRESETS = {
    # Calido y cercano: La bemol mayor con novena, campanas en registro medio.
    "autumn": {
        "pad": [(103.83, 0.85),    # A|b2  fundamental
                (155.56, 0.55),    # E|b3  quinta
                (261.63, 0.42),    # C4    tercera
                (392.00, 0.26),    # G4    septima mayor
                (466.16, 0.20)],   # B|b4  novena
        "bass": 51.91,             # A|b1
        "bells": [415.30, 466.16, 523.25, 622.25, 698.46,
                  830.61, 932.33, 1046.50],          # pentatonica A|b
        "n_bells": 11, "decay": 2.4, "wet": 0.42,
        "mix": (0.46, 0.13, 1.00, 0.05),             # pad, sub, campanas, viento
        "wind": (260.0, 2100.0),
    },
    # Frio y espacioso: Re menor con novena, campanas una octava mas arriba y
    # cola de reverb mas larga, que es lo que da la sensacion de intemperie.
    "aurora": {
        "pad": [(146.83, 0.80),    # D3    fundamental
                (220.00, 0.52),    # A3    quinta
                (349.23, 0.40),    # F4    tercera menor
                (523.25, 0.24),    # C5    septima
                (659.26, 0.19)],   # E5    novena
        "bass": 73.42,             # D2
        "bells": [587.33, 698.46, 783.99, 880.00, 1046.50,
                  1174.66, 1396.91, 1567.98],        # pentatonica de Re menor
        # wet 0.44 y no mas: la reverb es lo unico decorrelado entre canales,
        # asi que subirla gana espacio en auriculares y pierde nivel en mono.
        "n_bells": 8, "decay": 3.6, "wet": 0.44,
        "mix": (0.44, 0.11, 0.92, 0.07),
        "wind": (320.0, 3200.0),
    },
    # Melancolico y cercano: Sol menor con novena. Mas campanas y mas juntas
    # que en las otras dos, para que dialoguen con las gotas de la imagen.
    "rain": {
        "pad": [(98.00, 0.82),     # G2    fundamental
                (146.83, 0.54),    # D3    quinta
                (233.08, 0.42),    # B|b3  tercera menor
                (349.23, 0.26),    # F4    septima
                (440.00, 0.20)],   # A4    novena
        "bass": 49.00,             # G1
        "bells": [392.00, 466.16, 523.25, 587.33, 698.46,
                  783.99, 932.33, 1046.50],          # pentatonica de Sol menor
        "n_bells": 14, "decay": 2.8, "wet": 0.46,
        "mix": (0.45, 0.12, 0.88, 0.06),
        "wind": (280.0, 2600.0),
    },
    # Cinematografico y grave: Do menor, con PROGRESION de acordes y un motivo
    # melodico escrito en vez de campanas al azar. Pedal de Do debajo de todo:
    # la armonia se mueve y la fundamental no, que es justo la sensacion de
    # algo que atrae y no suelta. Cierra con riser + golpe en la costura.
    "horizon": {
        # i - VI - iv - VII sobre Do menor (Cm add9, A|bmaj9, Fm9, B|b add9)
        "prog": [
            [(65.41, 0.88), (98.00, 0.58), (155.56, 0.46), (196.00, 0.30), (293.66, 0.22)],
            [(51.91, 0.88), (77.78, 0.58), (130.81, 0.46), (196.00, 0.30), (233.08, 0.22)],
            [(43.65, 0.88), (65.41, 0.58), (103.83, 0.46), (155.56, 0.30), (196.00, 0.24)],
            [(58.27, 0.88), (87.31, 0.58), (146.83, 0.46), (174.61, 0.30), (261.63, 0.22)],
        ],
        # Pedal de Do2 y no Do1: eq_tilt corta debajo de 45 Hz, asi que un
        # pedal en 32.7 Hz no llega a existir en un telefono. En 65.4 se
        # escucha, y Do cae bien sobre los cuatro acordes (fundamental, tercera
        # de A|b, quinta de Fm, novena de B|b).
        "bass": 65.41,
        # (beat, duracion en beats, frecuencia) sobre 16 beats = un ciclo
        "melody": [(0.0, 2.0, 392.00), (2.0, 1.0, 311.13), (3.0, 1.0, 349.23),
                   (4.0, 2.0, 311.13), (6.0, 2.0, 261.63),
                   (8.0, 2.0, 415.30), (10.0, 1.0, 392.00), (11.0, 1.0, 349.23),
                   (12.0, 3.0, 392.00), (15.0, 1.0, 233.08)],
        "beats": 16, "mel_decay": 1.9,
        "bells": [523.25, 622.25, 698.46, 783.99, 932.33, 1046.50],
        "n_bells": 5, "decay": 4.2, "wet": 0.40,
        # pad, sub, campanas, viento, melodia, golpe. La melodia va POR ENCIMA
        # del pad: a 3 dB por debajo se la come el colchon y deja de ser una
        # melodia para volver a ser atmosfera.
        "mix": (0.34, 0.34, 0.48, 0.09, 1.05, 0.50),
        "wind": (400.0, 5200.0),
    },
    # Luminoso y ascendente: Mi bemol mayor, I-vi-IV-V, pedal de Si bemol.
    # Misma maquinaria que "horizon" pero en mayor y sin el golpe al frente:
    # aca la pieza acompana algo que CRECE, no algo que traga.
    "bloom": {
        "prog": [
            [(77.78, 0.86), (116.54, 0.56), (196.00, 0.46), (233.08, 0.30), (349.23, 0.22)],
            [(65.41, 0.86), (98.00, 0.56), (155.56, 0.46), (233.08, 0.30), (293.66, 0.22)],
            [(51.91, 0.86), (77.78, 0.56), (130.81, 0.46), (196.00, 0.30), (233.08, 0.22)],
            [(58.27, 0.86), (87.31, 0.56), (146.83, 0.46), (174.61, 0.30), (261.63, 0.22)],
        ],
        # Pedal de Si bemol2 y no 1: en 58 Hz el corte de retumbe de eq_tilt
        # se lo come casi entero. Quinta de Mi bemol, septima de Do menor,
        # novena de La bemol: cae bien sobre los cuatro acordes.
        "bass": 116.54,
        "melody": [(0.0, 2.0, 466.16), (2.0, 1.0, 392.00), (3.0, 1.0, 415.30),
                   (4.0, 2.0, 392.00), (6.0, 2.0, 311.13),
                   (8.0, 2.0, 523.25), (10.0, 1.0, 466.16), (11.0, 1.0, 415.30),
                   (12.0, 2.0, 466.16), (14.0, 1.0, 349.23), (15.0, 1.0, 392.00)],
        "beats": 16, "mel_decay": 2.1,
        "bells": [622.25, 698.46, 783.99, 932.33, 1046.50, 1244.51],
        "n_bells": 7, "decay": 3.8, "wet": 0.42,
        # pad, sub, campanas, viento, melodia, golpe
        "mix": (0.34, 0.30, 0.52, 0.08, 1.00, 0.22),
        "wind": (420.0, 5400.0),
    },
    # Flotante y sin resolver: Re dorico, i-IV-i-bVII. El cuarto grado MAYOR
    # sobre una tonica menor es lo que da el color dorico, y la progresion no
    # cierra nunca: acompana una figura que gira sin llegar a ningun lado.
    "drift": {
        "prog": [
            [(73.42, 0.86), (110.00, 0.56), (174.61, 0.46), (261.63, 0.30), (329.63, 0.22)],
            [(98.00, 0.86), (146.83, 0.56), (246.94, 0.46), (329.63, 0.30), (440.00, 0.20)],
            [(73.42, 0.86), (110.00, 0.56), (174.61, 0.46), (261.63, 0.30), (329.63, 0.22)],
            [(65.41, 0.86), (98.00, 0.56), (164.81, 0.46), (246.94, 0.30), (293.66, 0.22)],
        ],
        "bass": 73.42,             # pedal de Re2 bajo los cuatro acordes
        "melody": [(0.0, 2.0, 440.00), (2.0, 1.0, 349.23), (3.0, 1.0, 392.00),
                   (4.0, 2.0, 493.88), (6.0, 2.0, 440.00),
                   (8.0, 2.0, 587.33), (10.0, 1.0, 523.25), (11.0, 1.0, 440.00),
                   (12.0, 2.0, 392.00), (14.0, 1.0, 329.63), (15.0, 1.0, 293.66)],
        "beats": 16, "mel_decay": 2.2,
        "bells": [587.33, 659.26, 783.99, 880.00, 987.77, 1174.66],
        "n_bells": 8, "decay": 4.0, "wet": 0.43,
        # pad, sub, campanas, viento, melodia, golpe
        "mix": (0.34, 0.30, 0.46, 0.08, 1.02, 0.30),
        "wind": (400.0, 5000.0),
    },
    # Mecanico y circular: La menor, i-v-VI-III, con OSTINATO de corcheas en
    # vez de melodia sostenida. Una permutacion que vuelve a su punto de
    # partida pide un motivo de relojeria, no una linea que respire.
    "lattice": {
        "prog": [
            [(110.00, 0.86), (164.81, 0.56), (261.63, 0.46), (392.00, 0.28), (493.88, 0.20)],
            [(82.41, 0.86), (123.47, 0.56), (164.81, 0.46), (196.00, 0.28), (293.66, 0.20)],
            [(87.31, 0.86), (130.81, 0.56), (220.00, 0.46), (329.63, 0.28), (392.00, 0.20)],
            [(65.41, 0.86), (98.00, 0.56), (164.81, 0.46), (246.94, 0.28), (293.66, 0.20)],
        ],
        "bass": 110.00,            # pedal de La2 bajo los cuatro acordes
        "melody": [(0.0, 0.5, 440.0),
                   (0.5, 0.5, 523.25),
                   (1.0, 0.5, 659.26),
                   (1.5, 0.5, 523.25),
                   (2.0, 0.5, 440.0),
                   (2.5, 0.5, 523.25),
                   (3.0, 0.5, 659.26),
                   (3.5, 0.5, 523.25),
                   (4.0, 0.5, 493.88),
                   (4.5, 0.5, 587.33),
                   (5.0, 0.5, 659.26),
                   (5.5, 0.5, 587.33),
                   (6.0, 0.5, 493.88),
                   (6.5, 0.5, 587.33),
                   (7.0, 0.5, 659.26),
                   (7.5, 0.5, 587.33),
                   (8.0, 0.5, 440.0),
                   (8.5, 0.5, 523.25),
                   (9.0, 0.5, 698.46),
                   (9.5, 0.5, 523.25),
                   (10.0, 0.5, 440.0),
                   (10.5, 0.5, 523.25),
                   (11.0, 0.5, 698.46),
                   (11.5, 0.5, 523.25),
                   (12.0, 0.5, 392.0),
                   (12.5, 0.5, 493.88),
                   (13.0, 0.5, 659.26),
                   (13.5, 0.5, 493.88),
                   (14.0, 0.5, 392.0),
                   (14.5, 0.5, 493.88),
                   (15.0, 0.5, 659.26),
                   (15.5, 0.5, 493.88)],
        "beats": 16, "mel_decay": 0.85,
        "bells": [659.26, 783.99, 880.00, 1046.50, 1318.51],
        "n_bells": 6, "decay": 3.4, "wet": 0.38,
        # pad, sub, campanas, viento, melodia, golpe
        "mix": (0.32, 0.30, 0.34, 0.07, 0.78, 0.34),
        "wind": (420.0, 5000.0),
    },
    # Vasto y con pulso: Si menor, i-VI-III-VII, pedal de Fa# bajo los cuatro.
    # La "melodia" no es una linea sino un BLIP corto y agudo cada dos tiempos,
    # con la altura cambiando por acorde: un pulsar es un reloj y la pieza
    # tenia que sonar como uno.
    "beacon": {
        "prog": [
            [(61.74, 0.88), (92.50, 0.56), (146.83, 0.46), (220.00, 0.28), (277.18, 0.20)],
            [(49.00, 0.88), (73.42, 0.56), (123.47, 0.46), (185.00, 0.28), (220.00, 0.20)],
            [(73.42, 0.88), (110.00, 0.56), (185.00, 0.46), (220.00, 0.28), (329.63, 0.20)],
            [(55.00, 0.88), (82.41, 0.56), (138.59, 0.46), (185.00, 0.28), (246.94, 0.20)],
        ],
        "bass": 92.50,             # pedal de Fa#2 bajo los cuatro acordes
        "melody": [(0.0, 0.35, 739.99), (2.0, 0.35, 739.99),
                   (4.0, 0.35, 587.33), (6.0, 0.35, 587.33),
                   (8.0, 0.35, 739.99), (10.0, 0.35, 739.99),
                   (12.0, 0.35, 659.26), (14.0, 0.35, 659.26)],
        "beats": 16, "mel_decay": 0.60,
        "bells": [493.88, 587.33, 739.99, 880.00, 1108.73],
        # wet 0.40 y no 0.44: la reverb es lo unico decorrelado entre canales
        # y con 0.44 la perdida al sumar a mono daba -1.14 dB, fuera de linea
        # con el resto de los presets. Los shorts se oyen en mono.
        "n_bells": 5, "decay": 4.6, "wet": 0.40,
        # pad, sub, campanas, viento, melodia, golpe
        "mix": (0.36, 0.30, 0.30, 0.08, 0.92, 0.32),
        "wind": (380.0, 4800.0),
    },
    # Amplio y en caida: Mi menor, i-VI-III-VII. La melodia baja en tres
    # frases sucesivas y solo al final vuelve a subir, que es exactamente lo
    # que hace el campo: se fragmenta, cae en escala y termina en unos pocos
    # remolinos grandes.
    "cascade": {
        "prog": [
            [(82.41, 0.86), (123.47, 0.56), (164.81, 0.46), (196.00, 0.30), (246.94, 0.22)],
            [(65.41, 0.86), (98.00, 0.56), (130.81, 0.46), (164.81, 0.30), (196.00, 0.22)],
            [(98.00, 0.86), (146.83, 0.56), (196.00, 0.46), (246.94, 0.30), (293.66, 0.22)],
            [(73.42, 0.86), (110.00, 0.56), (146.83, 0.46), (185.00, 0.30), (220.00, 0.22)],
        ],
        "bass": 82.41,             # pedal de Mi2; por debajo de 60 Hz el
        # filtro de inclinacion se lo come y en un telefono no queda nada
        "melody": [(0.0, 1.5, 987.77), (1.5, 0.5, 880.00), (2.0, 2.0, 783.99),
                   (4.0, 1.5, 659.26), (5.5, 0.5, 587.33), (6.0, 2.0, 523.25),
                   (8.0, 1.5, 587.33), (9.5, 0.5, 493.88), (10.0, 2.0, 392.00),
                   (12.0, 1.0, 440.00), (13.0, 1.0, 493.88), (14.0, 2.0, 587.33)],
        "beats": 16, "mel_decay": 2.4,
        "bells": [659.26, 783.99, 880.00, 987.77, 1174.66],
        "n_bells": 7, "decay": 4.4, "wet": 0.40,
        # pad, sub, campanas, viento, melodia, golpe
        "mix": (0.36, 0.30, 0.40, 0.09, 0.96, 0.28),
        "wind": (360.0, 5200.0),
    },
    # Nocturno y con pulso: Re mayor, I-vi-IV-V. La melodia es un pizzicato
    # en CADA tiempo, arpegiando el acorde. Con 16 tiempos en 15 s el pulso
    # cae cada 0.9375 s, que es exactamente el periodo natural medio de las
    # luciernagas del short de Kuramoto: cuando el enjambre se sincroniza,
    # destella encima de estas notas.
    "fireflies": {
        "prog": [
            [(73.42, 0.86), (110.00, 0.56), (146.83, 0.46), (185.00, 0.30), (220.00, 0.22)],
            [(61.74, 0.86), (92.50, 0.56), (123.47, 0.46), (146.83, 0.30), (185.00, 0.22)],
            [(98.00, 0.86), (146.83, 0.56), (196.00, 0.46), (246.94, 0.30), (293.66, 0.22)],
            [(110.00, 0.86), (164.81, 0.56), (220.00, 0.46), (277.18, 0.30), (329.63, 0.22)],
        ],
        "bass": 73.42,             # pedal de Re2
        "melody": [(0.0, 0.35, 739.99), (1.0, 0.35, 880.00),
                   (2.0, 0.35, 1174.66), (3.0, 0.35, 880.00),
                   (4.0, 0.35, 739.99), (5.0, 0.35, 987.77),
                   (6.0, 0.35, 1174.66), (7.0, 0.35, 987.77),
                   (8.0, 0.35, 783.99), (9.0, 0.35, 987.77),
                   (10.0, 0.35, 1174.66), (11.0, 0.35, 987.77),
                   (12.0, 0.35, 659.26), (13.0, 0.35, 880.00),
                   (14.0, 0.35, 1108.73), (15.0, 0.35, 880.00)],
        "beats": 16, "mel_decay": 0.70,
        "bells": [1174.66, 1318.51, 1479.98, 1760.00],
        "n_bells": 6, "decay": 4.2, "wet": 0.40,
        # pad, sub, campanas, viento, melodia, golpe
        "mix": (0.34, 0.28, 0.30, 0.10, 0.80, 0.26),
        "wind": (420.0, 5200.0),
    },
    # Epico y con pulso: La menor, i-VI-III-VII (Am-F-C-G). Melodia principal
    # que sube acorde tras acorde hasta el Re agudo del final, arpegio en
    # corcheas debajo a menos intensidad, bombo en cada tiempo y charles en el
    # contratiempo. Tres golpes graves marcan el video del cerebro de mosca:
    # el estimulo (1.8 s), la Fibra Gigante (4.35 s) y el salto (6.52 s). El
    # arco sube hasta el salto y vuelve al nivel de partida para cerrar.
    "ignite": {
        "prog": [
            [(110.00, 0.86), (164.81, 0.56), (220.00, 0.46), (261.63, 0.30), (329.63, 0.22)],
            [(87.31, 0.86), (130.81, 0.56), (174.61, 0.46), (220.00, 0.30), (261.63, 0.22)],
            [(65.41, 0.86), (98.00, 0.56), (130.81, 0.46), (164.81, 0.30), (196.00, 0.22)],
            [(98.00, 0.86), (146.83, 0.56), (196.00, 0.46), (246.94, 0.30), (293.66, 0.22)],
        ],
        "bass": 110.00,            # pedal de La2
        "melody": [(0.0, 0.5, 440.00, 0.4),
                   (0.0, 1.5, 659.26, 1.0),
                   (0.5, 0.5, 523.25, 0.4),
                   (1.0, 0.5, 659.26, 0.4),
                   (1.5, 0.5, 523.25, 0.4),
                   (1.5, 0.5, 587.33, 1.0),
                   (2.0, 0.5, 440.00, 0.4),
                   (2.0, 1.0, 523.25, 1.0),
                   (2.5, 0.5, 523.25, 0.4),
                   (3.0, 0.5, 659.26, 0.4),
                   (3.0, 1.0, 659.26, 1.0),
                   (3.5, 0.5, 523.25, 0.4),
                   (4.0, 0.5, 349.23, 0.4),
                   (4.0, 1.5, 698.46, 1.0),
                   (4.5, 0.5, 440.00, 0.4),
                   (5.0, 0.5, 523.25, 0.4),
                   (5.5, 0.5, 440.00, 0.4),
                   (5.5, 0.5, 659.26, 1.0),
                   (6.0, 0.5, 349.23, 0.4),
                   (6.0, 1.0, 523.25, 1.0),
                   (6.5, 0.5, 440.00, 0.4),
                   (7.0, 0.5, 523.25, 0.4),
                   (7.0, 1.0, 880.00, 1.0),
                   (7.5, 0.5, 440.00, 0.4),
                   (8.0, 0.5, 523.25, 0.4),
                   (8.0, 1.5, 783.99, 1.0),
                   (8.5, 0.5, 659.26, 0.4),
                   (9.0, 0.5, 783.99, 0.4),
                   (9.5, 0.5, 659.26, 0.4),
                   (9.5, 0.5, 659.26, 1.0),
                   (10.0, 0.5, 523.25, 0.4),
                   (10.0, 1.0, 783.99, 1.0),
                   (10.5, 0.5, 659.26, 0.4),
                   (11.0, 0.5, 783.99, 0.4),
                   (11.0, 1.0, 1046.50, 1.0),
                   (11.5, 0.5, 659.26, 0.4),
                   (12.0, 0.5, 392.00, 0.4),
                   (12.0, 1.0, 987.77, 1.0),
                   (12.5, 0.5, 493.88, 0.4),
                   (13.0, 0.5, 587.33, 0.4),
                   (13.0, 0.5, 880.00, 1.0),
                   (13.5, 0.5, 493.88, 0.4),
                   (13.5, 0.5, 783.99, 1.0),
                   (14.0, 0.5, 392.00, 0.4),
                   (14.0, 1.0, 987.77, 1.0),
                   (14.5, 0.5, 493.88, 0.4),
                   (15.0, 0.5, 587.33, 0.4),
                   (15.0, 1.0, 1174.66, 1.0),
                   (15.5, 0.5, 493.88, 0.4)],
        "beats": 16, "mel_decay": 1.4,
        "bells": [880.00, 1046.50, 1318.51, 1567.98],
        "n_bells": 5, "decay": 3.6, "wet": 0.36,
        # pad, sub, campanas, viento, melodia, golpe
        "mix": (0.40, 0.34, 0.18, 0.06, 1.05, 0.26),
        "wind": (400.0, 5200.0),
        "booms": [(1.80, 0.75), (4.35, 0.90), (6.52, 1.00)], "booms_mix": 0.55,
        "arc": [(0.0, 0.62), (1.8, 0.70), (6.5, 1.00), (13.2, 1.00), (15.0, 0.62)],
        "drive": [(0.0, 1.0, "k"), (0.5, 0.55, "h"), (1.0, 0.72, "k"), (1.5, 0.55, "h"), (2.0, 0.72, "k"), (2.5, 0.55, "h"), (3.0, 0.72, "k"), (3.5, 0.55, "h"), (4.0, 1.0, "k"), (4.5, 0.55, "h"), (5.0, 0.72, "k"), (5.5, 0.55, "h"), (6.0, 0.72, "k"), (6.5, 0.55, "h"), (7.0, 0.72, "k"), (7.5, 0.55, "h"), (8.0, 1.0, "k"), (8.5, 0.55, "h"), (9.0, 0.72, "k"), (9.5, 0.55, "h"), (10.0, 0.72, "k"), (10.5, 0.55, "h"), (11.0, 0.72, "k"), (11.5, 0.55, "h"), (12.0, 1.0, "k"), (12.5, 0.55, "h"), (13.0, 0.72, "k"), (13.5, 0.55, "h"), (14.0, 0.72, "k"), (14.5, 0.55, "h"), (15.0, 0.72, "k"), (15.5, 0.55, "h")],
        "drive_mix": 0.42,
        "drive_arc": [(0.0, 0.0), (1.6, 0.0), (2.4, 0.55), (6.5, 1.0), (12.8, 1.0),
                      (14.6, 0.0), (15.0, 0.0)],
    },
    # Misterio y colapso: Mi menor, i-VI-iv-V (Em-C-Am-B). Antes del colapso
    # solo pad y una linea lenta, sin percusion: la onda viaja. En el colapso
    # (6.0 s) un golpe grave y un Si agudo; desde ahi entra el pulso y un
    # arpegio que acompana la lluvia de electrones, con la sensible (Re#)
    # resolviendo en Mi al cerrar el bucle.
    "collapse": {
        "prog": [
            [(82.41, 0.86), (123.47, 0.56), (164.81, 0.46), (196.00, 0.30), (246.94, 0.22)],
            [(65.41, 0.86), (98.00, 0.56), (130.81, 0.46), (164.81, 0.30), (196.00, 0.22)],
            [(110.00, 0.86), (164.81, 0.56), (220.00, 0.46), (261.63, 0.30), (329.63, 0.22)],
            [(61.74, 0.86), (92.50, 0.56), (123.47, 0.46), (155.56, 0.30), (185.00, 0.22)],
        ],
        "bass": 82.41,             # pedal de Mi2
        "melody": [
                   (0.0, 2.0, 493.88, 1.0),
                   (2.0, 1.0, 440.00, 0.8),
                   (3.0, 1.0, 392.00, 0.8),
                   (4.0, 2.0, 659.26, 1.0),
                   (6.4, 1.2, 987.77, 1.0),
                   (7.0, 0.5, 261.63, 0.4),
                   (7.0, 1.0, 783.99, 1.0),
                   (7.5, 0.5, 329.63, 0.4),
                   (8.0, 0.5, 220.00, 0.4),
                   (8.0, 1.5, 880.00, 1.0),
                   (8.5, 0.5, 261.63, 0.4),
                   (9.0, 0.5, 329.63, 0.4),
                   (9.5, 0.5, 261.63, 0.4),
                   (9.5, 0.5, 783.99, 1.0),
                   (10.0, 0.5, 220.00, 0.4),
                   (10.0, 1.0, 659.26, 1.0),
                   (10.5, 0.5, 261.63, 0.4),
                   (11.0, 0.5, 329.63, 0.4),
                   (11.0, 1.0, 1046.50, 1.0),
                   (11.5, 0.5, 440.00, 0.4),
                   (12.0, 0.5, 246.94, 0.4),
                   (12.0, 1.0, 987.77, 1.0),
                   (12.5, 0.5, 311.13, 0.4),
                   (13.0, 0.5, 369.99, 0.4),
                   (13.0, 0.5, 880.00, 1.0),
                   (13.5, 0.5, 311.13, 0.4),
                   (13.5, 0.5, 739.99, 1.0),
                   (14.0, 0.5, 246.94, 0.4),
                   (14.0, 1.0, 622.25, 1.0),
                   (14.5, 0.5, 311.13, 0.4),
                   (15.0, 0.5, 369.99, 0.4),
                   (15.0, 1.0, 659.26, 1.0),
                   (15.5, 0.5, 493.88, 0.4)],
        "beats": 16, "mel_decay": 1.5,
        "bells": [987.77, 1318.51, 1479.98, 1975.53],
        "n_bells": 6, "decay": 4.0, "wet": 0.40,
        # pad, sub, campanas, viento, melodia, golpe
        "mix": (0.42, 0.34, 0.22, 0.08, 1.0, 0.26),
        "wind": (380.0, 5200.0),
        "booms": [(6.00, 1.00)], "booms_mix": 0.60,
        "arc": [(0.0, 0.58), (5.9, 0.82), (6.1, 1.00), (13.4, 1.00), (15.0, 0.58)],
        "drive_mix": 0.42,
        # antes del colapso no hay golpes en el patron: el arco solo recoge el cierre
        "drive_arc": [(0.0, 0.3), (6.0, 1.0), (13.4, 1.0), (15.0, 0.3)],
        "drive": [(7.0, 0.72, "k"), (7.5, 0.55, "h"), (8.0, 1.0, "k"), (8.5, 0.55, "h"), (9.0, 0.72, "k"), (9.5, 0.55, "h"), (10.0, 0.72, "k"), (10.5, 0.55, "h"), (11.0, 0.72, "k"), (11.5, 0.55, "h"), (12.0, 1.0, "k"), (12.5, 0.55, "h"), (13.0, 0.72, "k"), (13.5, 0.55, "h"), (14.0, 0.72, "k"), (14.5, 0.55, "h"), (15.0, 0.72, "k"), (15.5, 0.55, "h")],
    },
    # Epico: Re menor, i-VI-iv-V (Dm-Bb-Gm-A). Ostinato de cuerdas en
    # semicorcheas, metales con el tema, taikos, platillos y subidas. Dos
    # golpes marcan el video de la doble rendija: el colapso del primer
    # electron (3.75 s, tiempo 4) y el giro cuando se encienden los detectores
    # (9.375 s, tiempo 10), precedido de medio tiempo de silencio.
    "titan": {
        "prog": [
            [(73.42, 0.86), (110.00, 0.56), (146.83, 0.46), (174.61, 0.30), (220.00, 0.22)],
            [(58.27, 0.86), (87.31, 0.56), (116.54, 0.46), (146.83, 0.30), (174.61, 0.22)],
            [(98.00, 0.86), (146.83, 0.56), (196.00, 0.46), (233.08, 0.30), (293.66, 0.22)],
            [(110.00, 0.86), (164.81, 0.56), (220.00, 0.46), (277.18, 0.30), (329.63, 0.22)],
        ],
        "bass": 73.42,             # pedal de Re2
        "melody": [(4.0, 0.5, 1174.66, 0.5), (6.0, 0.5, 1396.91, 0.4),
                   (10.0, 0.5, 1567.98, 0.6), (12.0, 0.5, 1318.51, 0.5)],
        "beats": 16, "mel_decay": 1.2,
        "bells": [1174.66, 1396.91, 1760.00],
        "n_bells": 4, "decay": 2.8, "wet": 0.32,
        # pad, sub, campanas, viento, melodia, golpe
        "mix": (0.38, 0.30, 0.10, 0.05, 0.35, 0.0),
        "wind": (400.0, 5200.0),
        "booms": [(3.75, 0.90), (9.375, 1.00)], "booms_mix": 0.55,
        "arc": [(0.0, 0.60), (3.70, 0.80), (3.75, 1.00), (8.85, 1.00), (8.95, 0.20),
                (9.36, 0.20), (9.375, 1.00), (14.3, 1.00), (15.0, 0.60)],
        "epic": {
            # cuerdas, metales, taikos, platillos, subidas
            "mix": (0.55, 0.75, 0.85, 0.22, 0.35),
            "arc": [(0.0, 0.55), (3.70, 0.75), (3.75, 1.00), (8.85, 1.00), (8.92, 0.08),
                    (9.36, 0.08), (9.375, 1.15), (14.3, 1.15), (15.0, 0.55)],
            "strings": [(0.0, 0.25, 146.83), (0.25, 0.15, 146.83), (0.5, 0.206, 220.0), (0.75, 0.174, 146.83), (1.0, 0.338, 293.66), (1.25, 0.198, 146.83), (1.5, 0.267, 220.0), (1.75, 0.222, 174.61), (2.0, 0.425, 146.83), (2.25, 0.246, 146.83), (2.5, 0.328, 220.0), (2.75, 0.27, 146.83), (3.0, 0.512, 293.66), (3.25, 0.294, 146.83), (3.5, 0.389, 220.0), (3.75, 0.318, 174.61), (4.0, 0.6, 116.54), (4.25, 0.34, 116.54), (4.5, 0.445, 174.61), (4.75, 0.36, 116.54), (5.0, 0.673, 233.08), (5.25, 0.38, 116.54), (5.5, 0.496, 174.61), (5.75, 0.4, 146.83), (6.0, 0.745, 116.54), (6.25, 0.42, 116.54), (6.5, 0.547, 174.61), (6.75, 0.44, 116.54), (7.0, 0.818, 233.08), (7.25, 0.46, 116.54), (7.5, 0.598, 174.61), (7.75, 0.48, 146.83), (8.0, 0.891, 98.0), (8.25, 0.5, 98.0), (8.5, 0.649, 146.83), (8.75, 0.52, 98.0), (9.0, 0.964, 196.0), (9.25, 0.54, 98.0), (10.0, 1.0, 98.0), (10.0, 0.5, 196.0), (10.25, 0.55, 98.0), (10.25, 0.275, 196.0), (10.5, 0.7, 146.83), (10.5, 0.35, 293.66), (10.75, 0.55, 98.0), (10.75, 0.275, 196.0), (11.0, 1.0, 196.0), (11.0, 0.5, 392.0), (11.25, 0.55, 98.0), (11.25, 0.275, 196.0), (11.5, 0.7, 146.83), (11.5, 0.35, 293.66), (11.75, 0.55, 116.54), (11.75, 0.275, 233.08), (12.0, 1.0, 110.0), (12.0, 0.5, 220.0), (12.25, 0.55, 110.0), (12.25, 0.275, 220.0), (12.5, 0.7, 164.81), (12.5, 0.35, 329.62), (12.75, 0.55, 110.0), (12.75, 0.275, 220.0), (13.0, 1.0, 220.0), (13.0, 0.5, 440.0), (13.25, 0.55, 110.0), (13.25, 0.275, 220.0), (13.5, 0.7, 164.81), (13.5, 0.35, 329.62), (13.75, 0.55, 138.59), (13.75, 0.275, 277.18), (14.0, 1.0, 110.0), (14.0, 0.5, 220.0), (14.25, 0.55, 110.0), (14.25, 0.275, 220.0), (14.5, 0.7, 164.81), (14.5, 0.35, 329.62), (14.75, 0.55, 110.0), (14.75, 0.275, 220.0), (15.0, 1.0, 220.0), (15.0, 0.5, 440.0), (15.25, 0.55, 110.0), (15.25, 0.275, 220.0), (15.5, 0.7, 164.81), (15.5, 0.35, 329.62), (15.75, 0.55, 138.59), (15.75, 0.275, 277.18)],
            "brass": [(0, 2, 293.66, 0.45), (2, 1, 349.23, 0.5), (3, 1, 440.0, 0.6), (4, 1.5, 466.16, 1.0), (5.5, 0.5, 440.0, 0.9), (6, 1, 349.23, 0.9), (7, 1, 587.33, 1.0), (8, 1, 587.33, 1.0), (9, 0.5, 466.16, 0.9), (10, 1.5, 783.99, 1.0), (11.5, 0.5, 698.46, 1.0), (12, 1.5, 659.26, 1.0), (13.5, 0.5, 554.37, 1.0), (14, 1, 440.0, 0.9), (15, 0.5, 659.26, 0.8), (15.5, 0.5, 554.37, 0.7)],
            "taiko": [(1, 0.35), (2, 0.45), (3, 0.55), (3.5, 0.6), (3.75, 0.7), (4, 1.0), (4.5, 0.5), (5.0, 0.85), (5.5, 0.5), (6.0, 0.85), (6.5, 0.5), (7.0, 0.85), (7.5, 0.5), (8.0, 0.85), (8.5, 0.55), (8.75, 0.7), (9.0, 0.85), (9.25, 1.0), (10, 1.0), (10.5, 0.6), (11.0, 0.9), (11.5, 0.6), (12.0, 0.9), (12.5, 0.6), (13.0, 0.9), (13.5, 0.6), (14.0, 0.9), (14.5, 0.6), (15.0, 0.9), (15.5, 0.6), (14.25, 0.45), (14.75, 0.45), (15.25, 0.45), (15.75, 0.45)],
            "crash": [(3.75, 1.0), (9.375, 1.0), (13.125, 0.5)],
            "risers": [(2.2, 3.75), (7.4, 9.375)],
        },
    },
}


def snap(f: float, T: float) -> float:
    """Al multiplo mas cercano de 1/T: condicion para que el ciclo cierre."""
    return max(1.0, round(f * T)) / T


def pad(t, T, rng, voices):
    """Colchon armonico: cada voz con armonicos y tres copias desafinadas."""
    sig = np.zeros_like(t)
    for f0, amp in voices:
        for h, hamp in ((1, 1.0), (2, 0.34), (3, 0.15), (4, 0.07), (5, 0.035)):
            for cents in (-4.0, 0.0, 4.0):
                f = snap(f0 * h * (2.0 ** (cents / 1200.0)), T)
                ph = rng.uniform(0, 2 * np.pi)
                # respiracion lenta, en ciclos enteros para no romper el loop
                k = int(rng.integers(1, 4))
                lfo = 1.0 + 0.13 * np.sin(2 * np.pi * k * t / T + rng.uniform(0, 6.28))
                sig += amp * hamp * 0.33 * lfo * np.sin(2 * np.pi * f * t + ph)
    return sig


def sub(t, T, bass):
    f = snap(bass, T)
    swell = 0.75 + 0.25 * np.sin(2 * np.pi * 1.0 * t / T - 1.2)
    return swell * (np.sin(2 * np.pi * f * t) + 0.28 * np.sin(2 * np.pi * snap(f * 2, T) * t))


def bells(n, T, rng, scale, n_events):
    """Campanas de la pentatonica, sumadas con envolvente circular."""
    out = np.zeros(n)
    tail = int(2.8 * SR)
    tt = np.arange(tail) / SR
    # tiempos escalonados con jitter: ni metronomo ni azar puro
    starts = (np.linspace(0.0, T, n_events, endpoint=False)
              + rng.uniform(-0.35, 0.35, n_events)) % T
    for k, st in enumerate(sorted(starts)):
        f = scale[int(rng.integers(len(scale)))]
        env = np.exp(-tt * (2.1 + 0.6 * rng.random()))
        # parciales ligeramente inarmonicos: lo que hace que suene a metal
        v = np.zeros(tail)
        for mult, a in ((1.0, 1.0), (2.01, 0.42), (3.03, 0.18), (4.16, 0.08)):
            v += a * np.sin(2 * np.pi * f * mult * tt + rng.uniform(0, 6.28))
        v *= env * (0.55 + 0.45 * rng.random())
        i0 = int(st * SR)
        idx = (np.arange(tail) + i0) % n          # envoltura: la cola vuelve al inicio
        np.add.at(out, idx, v)
    return out


def chord_env(t, T, i, k, fade=0.40):
    """Ventana del acorde i de k, periodica en T.

    La cola del ultimo acorde se envuelve al principio, asi que el cruce entre
    la ultima y la primera armonia es el mismo crossfade que el resto: el loop
    cierra sin corte.
    """
    seg = T / k
    x = np.mod(t - i * seg, T)
    e = np.clip(np.minimum(x / fade, (seg + fade - x) / fade), 0.0, 1.0)
    return e * e * (3.0 - 2.0 * e)


def pad_prog(t, T, rng, prog, fade=0.40):
    """Pad con progresion: cada acorde con su ventana, sumados con solape."""
    sig = np.zeros_like(t)
    for i, voices in enumerate(prog):
        sig += chord_env(t, T, i, len(prog), fade) * pad(t, T, rng, voices)
    return sig


def melody(n, T, rng, notes, beats, decay=1.9):
    """Motivo ESCRITO, no campanas al azar: es lo que hace que se recuerde.

    Timbre de celesta -- parciales casi armonicos, ataque corto y cola larga --
    y una octava arriba por encima para que brille en parlante de telefono. La
    envoltura se suma en circular, igual que las campanas.
    """
    out = np.zeros(n)
    beat = T / beats
    tail = int(min(3.4, T) * SR)
    tt = np.arange(tail) / SR
    for note in notes:
        start, dur, f0 = note[:3]
        f0 = snap(f0, T)
        env = np.exp(-tt / (decay * (0.55 + 0.45 * dur / 2.0)))
        env *= np.clip(tt / 0.012, 0.0, 1.0)          # ataque, sin click
        v = np.zeros(tail)
        for mult, a in ((1.0, 1.0), (2.0, 0.30), (3.0, 0.12), (4.02, 0.05)):
            v += a * np.sin(2 * np.pi * f0 * mult * tt)
        v += 0.26 * np.sin(2 * np.pi * snap(f0 * 2.0, T) * tt) * np.exp(-tt / (decay * 0.6))
        v *= env
        if len(note) > 3:                             # intensidad opcional
            v *= note[3]
        idx = (np.arange(tail) + int(start * beat * SR)) % n
        np.add.at(out, idx, v)
    return out / (np.max(np.abs(out)) or 1.0)


def impact(n, T, rng, lo=52.0, hi=190.0, boom=2.4, rise=2.8):
    """Golpe grave en t=0 y riser que muere justo antes: cierra el ciclo.

    El riser termina en t=T y el golpe arranca en t=0, que en un loop son el
    mismo instante: el gesto queda entero cada vuelta en vez de cortarse.

    El barrido va de 190 a 52 Hz y no a 27: eq_tilt corta 13 dB debajo de 45 Hz
    (retumbe que en un telefono es silencio), asi que un sub-drop de manual se
    perderia entero. En este rango pega igual y sobrevive al parlante chico.
    """
    out = np.zeros(n)
    nb = min(n, int(boom * SR))
    x = np.arange(nb) / SR
    # barrido descendente de frecuencia: fase = integral de f(x)
    k = np.log(lo / hi) / boom
    ph = 2 * np.pi * hi * (np.exp(k * x) - 1.0) / k
    out[:nb] += np.sin(ph) * np.exp(-x / 0.62)
    out[:nb] += 0.16 * rng.normal(0, 1, nb) * np.exp(-x / 0.045)   # transitorio

    nr = min(n, int(rise * SR))
    y = np.arange(nr) / SR
    frac = y / rise
    # ruido con centro que sube: se sintetiza como un barrido de fase sobre
    # ruido filtrado barato, y se apaga en los ultimos 8 ms para no chasquear
    ns = rng.normal(0, 1, nr)
    ns = np.cumsum(ns); ns -= np.linspace(ns[0], ns[-1], nr)       # paso-bajo + sin DC
    ns /= (np.max(np.abs(ns)) or 1.0)
    swirl = np.sin(2 * np.pi * (120.0 * y + 600.0 * y * frac))
    r = (0.55 * ns + 0.45 * swirl) * frac ** 2.6
    r *= np.clip((rise - y) / 0.008, 0.0, 1.0)
    out[n - nr:] += 1.55 * r
    return out / (np.max(np.abs(out)) or 1.0)


def drive(n, T, rng, pattern, beats):
    """Pulso: bombo y charles. Cada golpe es (beat, intensidad, "k" o "h").

    El bombo barre de 140 a 58 Hz y no mas abajo, por el mismo motivo que el
    golpe de impact(): eq_tilt corta debajo de 45 Hz y en un telefono se
    perderia. Se suma en circular, como la melodia, para que el ciclo cierre.
    """
    out = np.zeros(n)
    beat = T / beats
    nk = int(0.45 * SR)
    x = np.arange(nk) / SR
    kk = np.log(58.0 / 140.0) / 0.09
    ph = 2 * np.pi * 140.0 * (np.exp(kk * np.minimum(x, 0.09)) - 1.0) / kk \
        + 2 * np.pi * 58.0 * np.maximum(x - 0.09, 0.0)
    kick = np.sin(ph) * np.exp(-x / 0.20) * np.clip(x / 0.002, 0, 1)
    kick += 0.35 * rng.normal(0, 1, nk) * np.exp(-x / 0.006)
    nh = int(0.12 * SR)
    hn = rng.normal(0, 1, nh + 1)
    hat = np.diff(hn) * np.exp(-np.arange(nh) / SR / 0.030) * 0.55
    for b, vel, kind in pattern:
        v = kick if kind == "k" else hat
        idx = (np.arange(len(v)) + int(b * beat * SR)) % n
        np.add.at(out, idx, vel * v)
    return out / (np.max(np.abs(out)) or 1.0)


def booms(n, T, rng, hits, lo=52.0, hi=200.0, boom=2.0):
    """Golpes graves sueltos en instantes dados (segundos), sin el riser de
    impact(): sirven para marcar momentos del video."""
    out = np.zeros(n)
    nb = min(n, int(boom * SR))
    x = np.arange(nb) / SR
    k = np.log(lo / hi) / boom
    ph = 2 * np.pi * hi * (np.exp(k * x) - 1.0) / k
    b = np.sin(ph) * np.exp(-x / 0.55) + 0.18 * rng.normal(0, 1, nb) * np.exp(-x / 0.04)
    for t0, g in hits:
        idx = (np.arange(nb) + int(t0 * SR)) % n
        np.add.at(out, idx, g * b)
    return out / (np.max(np.abs(out)) or 1.0)


def arc_env(t, T, pts):
    """Envolvente por tramos lineales (t, nivel). El primer y el ultimo nivel
    tienen que ser iguales: si no, el ciclo pega un salto en la costura."""
    ts = [p[0] for p in pts]
    vs = [p[1] for p in pts]
    assert abs(vs[0] - vs[-1]) < 1e-12 and ts[0] == 0.0 and abs(ts[-1] - T) < 1e-9, \
        "el arco tiene que empezar y terminar en el mismo nivel"
    return np.interp(t, ts, vs)


def _saw(f0, tt, top=5000.0):
    """diente de sierra de banda limitada: armonicos hasta 'top' Hz"""
    v = np.zeros_like(tt)
    for k in range(1, int(top // f0) + 1):
        v += np.sin(2 * np.pi * k * f0 * tt) / k * (1.0 / (1 + (k * f0 / 2400.0) ** 2))
    return v


def strings(n, T, notes, beats):
    """Ostinato de cuerdas en staccato: sierra filtrada, ataque de 6 ms y
    cola de 0.16 s. Cada nota es (beat, intensidad, Hz). Suma circular."""
    out = np.zeros(n)
    beat = T / beats
    nl = int(0.5 * SR)
    tt = np.arange(nl) / SR
    env = np.clip(tt / 0.006, 0, 1) * np.exp(-tt / 0.16)
    cache = {}
    for b, vel, f0 in notes:
        f0 = snap(f0, T)
        if f0 not in cache:
            # dos voces levemente desafinadas: seccion, no un solo instrumento
            cache[f0] = (_saw(f0, tt) + _saw(f0 * 1.004, tt)) * env
        idx = (np.arange(nl) + int(b * beat * SR)) % n
        np.add.at(out, idx, vel * cache[f0])
    return out / (np.max(np.abs(out)) or 1.0)


def brass(n, T, notes, beats):
    """Metales: sierra con ataque lento, vibrato que entra tarde y brillo que
    crece con la nota. Cada nota es (beat, duracion en beats, Hz, intensidad)."""
    out = np.zeros(n)
    beat = T / beats
    for b, dur, f0, vel in notes:
        f0 = snap(f0, T)
        L = dur * beat + 0.35
        tt = np.arange(int(L * SR)) / SR
        vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * tt) * np.clip((tt - 0.25) / 0.3, 0, 1)
        ph = 2 * np.pi * f0 * np.cumsum(vib) / SR
        v = np.zeros_like(tt)
        for k in range(1, 12):
            if k * f0 > 6000:
                break
            bright = np.clip(0.35 + 0.65 * tt / 0.25, 0, 1)
            v += np.sin(k * ph) / k ** (1.9 - 0.8 * bright)
        v += 0.5 * np.sin(0.5 * ph)                       # octava abajo
        env = np.clip(tt / 0.07, 0, 1) * np.clip((L - tt) / 0.30, 0, 1)
        idx = (np.arange(len(tt)) + int(b * beat * SR)) % n
        np.add.at(out, idx, vel * v * env)
    return out / (np.max(np.abs(out)) or 1.0)


def taiko(n, T, rng, hits, beats):
    """Tambor grande: membrana con modos inarmonicos que caen de tono, mas el
    golpe de la maza. Cada golpe es (beat, intensidad)."""
    out = np.zeros(n)
    beat = T / beats
    nl = int(0.9 * SR)
    x = np.arange(nl) / SR
    bend = 1 + 0.35 * np.exp(-x / 0.05)
    drum = np.zeros(nl)
    for m, a, d in ((1.0, 1.0, 0.42), (1.59, 0.45, 0.22), (2.14, 0.30, 0.14), (2.65, 0.18, 0.09)):
        ph = 2 * np.pi * 88.0 * m * np.cumsum(bend) / SR
        drum += a * np.sin(ph) * np.exp(-x / d)
    slap = rng.normal(0, 1, nl)
    slap = np.convolve(slap, np.ones(6) / 6, mode="same") * np.exp(-x / 0.018)
    drum = (drum + 0.9 * slap) * np.clip(x / 0.0015, 0, 1)
    for b, vel in hits:
        idx = (np.arange(nl) + int(b * beat * SR)) % n
        np.add.at(out, idx, vel * drum)
    return out / (np.max(np.abs(out)) or 1.0)


def crash(n, T, rng, hits):
    """Platillo: ruido brillante con cola larga. Golpes en segundos."""
    out = np.zeros(n)
    nl = int(2.2 * SR)
    x = np.arange(nl) / SR
    c = np.diff(rng.normal(0, 1, nl + 1)) * (np.exp(-x / 0.9) + 0.6 * np.exp(-x / 0.08))
    c *= np.clip(x / 0.002, 0, 1)
    for t0, g in hits:
        idx = (np.arange(nl) + int(t0 * SR)) % n
        np.add.at(out, idx, g * c)
    return out / (np.max(np.abs(out)) or 1.0)


def risers(n, T, rng, spans):
    """Subidas de tension que terminan justo en un golpe: ruido que se abre y
    un tono que sube una octava. Cada una es (inicio, fin) en segundos."""
    out = np.zeros(n)
    for t0, t1 in spans:
        nl = int((t1 - t0) * SR)
        y = np.arange(nl) / SR
        fr = y / (t1 - t0)
        ns = np.diff(rng.normal(0, 1, nl + 1))
        ns = np.convolve(ns, np.ones(3) / 3, mode="same")
        f = 220.0 * 2 ** (fr * 1.5)
        tone_ = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(4 * np.pi * np.cumsum(f) / SR)
        r = (0.6 * ns + 0.4 * tone_) * fr ** 2.4 * np.clip((t1 - t0 - y) / 0.006, 0, 1)
        idx = (np.arange(nl) + int(t0 * SR)) % n
        np.add.at(out, idx, r)
    return out / (np.max(np.abs(out)) or 1.0)


def wind(n, T, rng, lo=260.0, hi=2100.0):
    """Ruido moldeado sintetizado en frecuencia: periodico por definicion."""
    nf = n // 2 + 1
    freqs = np.arange(nf) / T
    mag = np.exp(-0.5 * ((np.log(np.clip(freqs, 1e-6, None) / np.sqrt(lo * hi))
                          / np.log(hi / lo)) ** 2) * 6.0)
    mag[freqs < 60] = 0.0
    spec = mag * np.exp(1j * rng.uniform(0, 2 * np.pi, nf))
    s = np.fft.irfft(spec, n)
    s /= (np.max(np.abs(s)) or 1.0)
    t = np.arange(n) / SR
    gust = 0.45 + 0.55 * (0.5 + 0.5 * np.sin(2 * np.pi * 2.0 * t / T - 0.7))
    return s * gust


def eq_tilt(sig, T):
    """Ecualizacion en el dominio de la frecuencia: quita retumbe y abre agudos.

    Sin esto la pieza concentra ~73% de la energia debajo de 400 Hz, que en el
    parlante de un telefono (que corta por debajo de 300 Hz) es casi silencio.
    Se hace sobre la FFT circular, asi que no rompe la periodicidad.
    """
    n = len(sig)
    f = np.clip(np.fft.rfftfreq(n, 1.0 / SR), 1e-3, None)
    lf = np.log10(f)
    db = (-13.0 * (1.0 - _smooth(lf, np.log10(45.0), np.log10(150.0)))      # retumbe
          - 3.5 * (1.0 - _smooth(lf, np.log10(150.0), np.log10(520.0)))     # barro
          + 7.0 * _smooth(lf, np.log10(700.0), np.log10(2600.0)))           # presencia
    return np.fft.irfft(np.fft.rfft(sig) * (10.0 ** (db / 20.0)), n)


def _smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def reverb(sig, T, rng, decay=2.4, wet=0.42):
    """Convolucion CIRCULAR: mantiene el loop exacto, a diferencia de la lineal."""
    n = len(sig)
    tt = np.arange(n) / SR
    ir = rng.normal(0.0, 1.0, n) * np.exp(-tt / decay)
    ir[0] += 6.0                                   # sonido directo
    ir /= np.sqrt(np.sum(ir * ir))
    out = np.fft.irfft(np.fft.rfft(sig) * np.fft.rfft(ir), n)
    return (1 - wet) * sig + wet * out * (np.max(np.abs(sig)) / (np.max(np.abs(out)) or 1.0))


def write_wav(path, left, right):
    data = np.stack([left, right], axis=1)
    peak = float(np.max(np.abs(data))) or 1.0
    data = (data / peak * 0.92 * 32767.0).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def compose(duration, preset="autumn", seed=7):
    """Contenido tonal identico en ambos canales; el ancho sale de la reverb.

    Decorrelar tambien las notas suena mas ancho en auriculares pero se cancela
    al sumar a mono, que es como se escucha la mayoria de los Shorts.
    """
    cfg = PRESETS[preset]
    T = float(duration)
    n = int(round(T * SR))
    t = np.arange(n) / SR
    g_pad, g_sub, g_bell, g_wind = cfg["mix"][:4]

    rng = np.random.default_rng(seed)
    if "prog" in cfg:
        # Pieza con progresion y motivo. Los presets sin "prog" siguen por el
        # camino de siempre y su salida no cambia.
        g_mel, g_hit = cfg["mix"][4], cfg["mix"][5]
        tonal = (g_pad * pad_prog(t, T, rng, cfg["prog"])
                 + g_sub * sub(t, T, cfg["bass"])
                 + g_bell * bells(n, T, rng, cfg["bells"], cfg["n_bells"])
                 + g_mel * melody(n, T, rng, cfg["melody"], cfg["beats"],
                                  cfg["mel_decay"])
                 + g_hit * impact(n, T, np.random.default_rng(seed + 991)))
        # capas opcionales: los presets que no las piden no cambian
        if "booms" in cfg:
            tonal = tonal + cfg["booms_mix"] * booms(
                n, T, np.random.default_rng(seed + 443), cfg["booms"])
        if "arc" in cfg:
            tonal = tonal * arc_env(t, T, cfg["arc"])
        if "drive" in cfg:
            tonal = tonal + cfg["drive_mix"] * arc_env(t, T, cfg["drive_arc"]) * drive(
                n, T, np.random.default_rng(seed + 557), cfg["drive"], cfg["beats"])
        if "epic" in cfg:
            # orquesta: cuerdas, metales, taikos, platillos y subidas. Van
            # despues del arco general, cada capa con su propio arco
            ep = cfg["epic"]
            env = arc_env(t, T, ep["arc"])
            tonal = tonal + env * (
                ep["mix"][0] * strings(n, T, ep["strings"], cfg["beats"])
                + ep["mix"][1] * brass(n, T, ep["brass"], cfg["beats"])
                + ep["mix"][2] * taiko(n, T, np.random.default_rng(seed + 661),
                                       ep["taiko"], cfg["beats"]))
            tonal = tonal + ep["mix"][3] * crash(
                n, T, np.random.default_rng(seed + 673), ep["crash"])
            tonal = tonal + ep["mix"][4] * risers(
                n, T, np.random.default_rng(seed + 683), ep["risers"])
    else:
        tonal = (g_pad * pad(t, T, rng, cfg["pad"])
                 + g_sub * sub(t, T, cfg["bass"])
                 + g_bell * bells(n, T, rng, cfg["bells"], cfg["n_bells"]))

    chans = []
    for ch in range(2):
        rw = np.random.default_rng(seed + 101 + ch)    # solo reverb y viento
        s = tonal + g_wind * wind(n, T, rw, *cfg["wind"])
        chans.append(eq_tilt(reverb(s, T, rw, cfg["decay"], cfg["wet"]), T))
    l, r = chans
    m = max(np.max(np.abs(l)), np.max(np.abs(r))) or 1.0
    return l / m, r / m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="autumn", choices=sorted(PRESETS))
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--name", default="music.wav")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    l, r = compose(a.duration, a.preset, a.seed)
    path = os.path.join(a.outdir, a.name)
    write_wav(path, l, r)
    print(f"[score] {a.duration:.2f}s | preset {a.preset} | loop exacto -> {path}")


if __name__ == "__main__":
    main()
