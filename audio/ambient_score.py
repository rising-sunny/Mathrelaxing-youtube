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
    for start, dur, f0 in notes:
        f0 = snap(f0, T)
        env = np.exp(-tt / (decay * (0.55 + 0.45 * dur / 2.0)))
        env *= np.clip(tt / 0.012, 0.0, 1.0)          # ataque, sin click
        v = np.zeros(tail)
        for mult, a in ((1.0, 1.0), (2.0, 0.30), (3.0, 0.12), (4.02, 0.05)):
            v += a * np.sin(2 * np.pi * f0 * mult * tt)
        v += 0.26 * np.sin(2 * np.pi * snap(f0 * 2.0, T) * tt) * np.exp(-tt / (decay * 0.6))
        v *= env
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
