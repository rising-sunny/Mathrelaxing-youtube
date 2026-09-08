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
    g_pad, g_sub, g_bell, g_wind = cfg["mix"]

    rng = np.random.default_rng(seed)
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
