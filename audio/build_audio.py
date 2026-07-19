"""
build_audio.py — Sonificación + drone para MathRelaxing.

Soporta múltiples atractores (lorenz, rossler) y genera:
  - drone.wav : pad ambiental.
  - hits.wav  : impactos de ataque lento.
"""

import argparse
import json
import os
import wave
import numpy as np

SR = 48000
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NOTE = {
    "C1": 32.70, "Eb1": 38.89, "G1": 49.00,
    "C2": 65.41, "Eb2": 77.78, "G2": 98.00,
    "C3": 130.81, "Eb3": 155.56, "G3": 196.00, "C4": 261.63,
}
LEVEL_TO_NOTE = {0.4: "C2", 0.8: "Eb2", 1.2: "G2"}


def write_wav_stereo(path, left, right):
    data = np.stack([left, right], axis=1)
    peak = float(np.max(np.abs(data))) or 1.0
    data = (data / peak * 0.89 * 32767.0).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def drone(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for name, detune, amp in [
        ("C2", 0.0, 1.0), ("G2", 0.3, 0.6), ("Eb3", -0.3, 0.5),
        ("C3", 0.2, 0.7), ("G3", 0.4, 0.3),
    ]:
        f = NOTE[name] * (1 + detune / 100.0)
        lfo = 1.0 + 0.05 * np.sin(2 * np.pi * 0.08 * t + amp)
        sig += amp * lfo * np.sin(2 * np.pi * f * t)
    env = np.ones(n)
    fade = int(min(0.6, dur / 4) * SR)
    env[:fade] = np.linspace(0, 1, fade) ** 2
    env[-fade:] = np.linspace(1, 0, fade) ** 2
    sig *= env
    return sig, np.roll(sig, int(0.004 * SR))


def hit(note_hz, gain=1.0, dur_tail=2.2, attractor="lorenz"):
    n = int(dur_tail * SR)
    t = np.arange(n) / SR
    
    if attractor == "thomas":
        atk = int(0.01 * SR)
        env = np.ones(n)
        env[:atk] = np.linspace(0, 1, atk)
        env[atk:] = np.exp(-3.0 * (t[atk:] - t[atk]))
        fund = np.sin(2 * np.pi * note_hz * t)
        harm1 = 0.5 * np.sin(2 * np.pi * note_hz * 2.76 * t) * np.exp(-4.0 * t)
        harm2 = 0.25 * np.sin(2 * np.pi * note_hz * 5.4 * t) * np.exp(-8.0 * t)
        return gain * env * (fund + harm1 + harm2)
    elif attractor == "pendulum":
        # Musical bell/vibraphone sound
        atk = int(0.005 * SR)
        env = np.ones(n)
        env[:atk] = np.linspace(0, 1, atk)
        env[atk:] = np.exp(-1.5 * (t[atk:] - t[atk]))
        fund = np.sin(2 * np.pi * note_hz * t)
        harm1 = 0.5 * np.sin(2 * np.pi * note_hz * 2.0 * t) * np.exp(-3.0 * t)
        harm2 = 0.25 * np.sin(2 * np.pi * note_hz * 4.0 * t) * np.exp(-5.0 * t)
        harm3 = 0.1 * np.sin(2 * np.pi * note_hz * 8.0 * t) * np.exp(-8.0 * t)
        return gain * env * (fund + harm1 + harm2 + harm3)
    elif attractor == "curl":
        # Water drop / soft pluck sound
        atk = int(0.008 * SR)
        env = np.ones(n)
        env[:atk] = np.linspace(0, 1, atk) ** 0.5
        env[atk:] = np.exp(-2.0 * (t[atk:] - t[atk]))
        fund = np.sin(2 * np.pi * note_hz * t)
        harm1 = 0.4 * np.sin(2 * np.pi * note_hz * 2.0 * t) * np.exp(-3.5 * t)
        harm2 = 0.15 * np.sin(2 * np.pi * note_hz * 3.0 * t) * np.exp(-5.0 * t)
        # Slight chorus / detuning for organic feel
        chorus = 0.2 * np.sin(2 * np.pi * note_hz * 1.003 * t) * np.exp(-2.5 * t)
        return gain * env * (fund + harm1 + harm2 + chorus)
    elif attractor == "tokamak":
        # Tokamak: deep resonant plasma sound
        atk = int(0.005 * SR)
        env = np.ones(n)
        env[:atk] = np.linspace(0, 1, atk) ** 0.5
        env[atk:] = np.exp(-1.5 * (t[atk:] - t[atk]))
        fund = np.sin(2 * np.pi * note_hz * t)
        harm1 = 0.5 * np.sin(2 * np.pi * note_hz * 2.0 * t) * np.exp(-3.0 * t)
        harm2 = 0.2 * np.sin(2 * np.pi * note_hz * 3.0 * t) * np.exp(-4.5 * t)
        pulse = 0.1 * np.sin(2 * np.pi * note_hz * 4.0 * t) * np.sin(2 * np.pi * 5 * t)
        return gain * env * (fund + harm1 + harm2 + pulse)
    elif attractor == "abc":
        # Resonant crystal / glass harmonic sound
        atk = int(0.003 * SR)
        env = np.ones(n)
        env[:atk] = np.linspace(0, 1, atk) ** 0.3
        env[atk:] = np.exp(-1.2 * (t[atk:] - t[atk]))
        fund = np.sin(2 * np.pi * note_hz * t)
        # Inharmonic partials for crystalline timbre
        harm1 = 0.6 * np.sin(2 * np.pi * note_hz * 2.24 * t) * np.exp(-2.0 * t)
        harm2 = 0.35 * np.sin(2 * np.pi * note_hz * 3.89 * t) * np.exp(-4.0 * t)
        harm3 = 0.15 * np.sin(2 * np.pi * note_hz * 6.27 * t) * np.exp(-7.0 * t)
        shimmer = 0.1 * np.sin(2 * np.pi * note_hz * 1.002 * t) * np.exp(-1.5 * t)
        return gain * env * (fund + harm1 + harm2 + harm3 + shimmer)
    elif attractor == "hopf":
        # Soft linked-fiber chime (linked circles of S³)
        atk = int(0.004 * SR)
        env = np.ones(n)
        env[:atk] = np.linspace(0, 1, atk) ** 0.4
        env[atk:] = np.exp(-1.0 * (t[atk:] - t[atk]))
        fund = np.sin(2 * np.pi * note_hz * t)
        harm1 = 0.55 * np.sin(2 * np.pi * note_hz * 2.0 * t) * np.exp(-1.8 * t)
        harm2 = 0.3 * np.sin(2 * np.pi * note_hz * 3.01 * t) * np.exp(-3.5 * t)
        harm3 = 0.12 * np.sin(2 * np.pi * note_hz * 5.0 * t) * np.exp(-6.0 * t)
        shimmer = 0.15 * np.sin(2 * np.pi * note_hz * 1.003 * t) * np.exp(-1.2 * t)
        return gain * env * (fund + harm1 + harm2 + harm3 + shimmer)
    elif attractor == "threebody":
        # Soft cosmic bell for orbital crossings
        atk = int(0.006 * SR)
        env = np.ones(n)
        env[:atk] = np.linspace(0, 1, atk) ** 0.5
        env[atk:] = np.exp(-1.3 * (t[atk:] - t[atk]))
        fund = np.sin(2 * np.pi * note_hz * t)
        harm1 = 0.45 * np.sin(2 * np.pi * note_hz * 2.0 * t) * np.exp(-2.2 * t)
        harm2 = 0.22 * np.sin(2 * np.pi * note_hz * 3.0 * t) * np.exp(-4.0 * t)
        harm3 = 0.1 * np.sin(2 * np.pi * note_hz * 4.5 * t) * np.exp(-6.5 * t)
        return gain * env * (fund + harm1 + harm2 + harm3)
    elif attractor == "clifford":
        # Soft hyperspace chime
        atk = int(0.005 * SR)
        env = np.ones(n)
        env[:atk] = np.linspace(0, 1, atk) ** 0.4
        env[atk:] = np.exp(-1.1 * (t[atk:] - t[atk]))
        fund = np.sin(2 * np.pi * note_hz * t)
        harm1 = 0.5 * np.sin(2 * np.pi * note_hz * 2.01 * t) * np.exp(-2.0 * t)
        harm2 = 0.28 * np.sin(2 * np.pi * note_hz * 3.5 * t) * np.exp(-3.8 * t)
        harm3 = 0.12 * np.sin(2 * np.pi * note_hz * 5.2 * t) * np.exp(-6.0 * t)
        shimmer = 0.12 * np.sin(2 * np.pi * note_hz * 1.004 * t) * np.exp(-1.4 * t)
        return gain * env * (fund + harm1 + harm2 + harm3 + shimmer)
    else:
        atk = int(0.18 * SR)
        env = np.ones(n)
        env[:atk] = np.linspace(0, 1, atk) ** 1.5
        env[atk:] = np.exp(-2.6 * (t[atk:] - t[atk]))
        fund = np.sin(2 * np.pi * note_hz * t)
        metal = 0.25 * np.sin(2 * np.pi * note_hz * 2.01 * t) + 0.12 * np.sin(2 * np.pi * note_hz * 3.0 * t)
        return gain * env * (fund + metal)


def resolve_note(ev):
    return ev.get("note") or LEVEL_TO_NOTE.get(ev.get("level"), "C2")


def add_echo(sig, delay_s=0.24, decay=0.5, taps=5):
    delay_n = int(delay_s * SR)
    out = np.copy(sig)
    for i in range(1, taps + 1):
        d = delay_n * i
        if d >= len(sig):
            break
        shifted = np.zeros_like(sig)
        shifted[d:] = sig[:-d]
        out += shifted * (decay ** i)
    return out


def eerie_bell(hz, gain=1.0, dur_tail=4.0):
    """Campana tetrica: una octava mas grave, armonicos ligeramente
    desafinados (disonancia sutil) y eco largo, en vez del vibrafono
    brillante original."""
    n = int(dur_tail * SR)
    t = np.arange(n) / SR
    hz_low = hz * 0.5

    atk = int(0.02 * SR)
    env = np.ones(n)
    env[:atk] = np.linspace(0, 1, atk)
    env[atk:] = np.exp(-1.0 * (t[atk:] - t[atk]))

    fund = np.sin(2 * np.pi * hz_low * t)
    dissonant1 = 0.40 * np.sin(2 * np.pi * hz_low * 1.98 * t) * np.exp(-1.6 * t)
    dissonant2 = 0.25 * np.sin(2 * np.pi * hz_low * 2.97 * t) * np.exp(-2.2 * t)
    sub = 0.55 * np.sin(2 * np.pi * hz_low * 0.5 * t) * np.exp(-0.8 * t)

    sig = gain * env * (fund + dissonant1 + dissonant2 + sub)
    return add_echo(sig, delay_s=0.24, decay=0.5, taps=5)


def bass_melody(dur, n_segments=15):
    """Linea de bajo melodica coherente (Do menor armonico), grave pero con
    contorno musical real -- una secuencia ascendente por terceras, no un
    glissando pegado a la frecuencia cruda de la fisica. Sincronizada con
    los cambios de nota (n_segments tramos iguales)."""
    n = int(dur * SR)
    seg_dur = dur / n_segments

    # Do menor armonico (grave, un poco tetrico), secuencia en terceras
    # que sube hasta un climax cerca del final.
    notes_hz = [
        65.41, 77.78, 73.42, 87.31, 77.78, 98.00, 87.31, 103.83,
        98.00, 123.47, 103.83, 130.81, 123.47, 155.56, 130.81,
    ]

    sig = np.zeros(n)
    for i in range(n_segments):
        f0 = notes_hz[i % len(notes_hz)]
        s0 = int(i * seg_dur * SR)
        s1 = int(min((i + 1) * seg_dur, dur) * SR)
        seg_n = s1 - s0
        if seg_n <= 0:
            continue
        t = np.arange(seg_n) / SR
        tone = (np.sin(2 * np.pi * f0 * t)
                + 0.35 * np.sin(2 * np.pi * f0 * 2 * t)
                + 0.15 * np.sin(2 * np.pi * f0 * 0.5 * t))

        atk = int(min(0.10, seg_dur * 0.25) * SR)
        rel = int(min(0.18, seg_dur * 0.3) * SR)
        env = np.ones(seg_n)
        if atk > 0:
            env[:atk] = np.linspace(0, 1, atk) ** 1.5
        if 0 < rel < seg_n:
            env[-rel:] *= np.linspace(1, 0, rel) ** 1.5

        sig[s0:s1] += tone[:seg_n] * env

    sig = add_echo(sig, delay_s=0.28, decay=0.35, taps=3)

    env_g = np.ones(n)
    fade = int(min(0.6, dur / 4) * SR)
    env_g[:fade] = np.linspace(0, 1, fade) ** 2
    env_g[-fade:] = np.linspace(1, 0, fade) ** 2
    sig *= env_g * 0.5

    pan = 0.5 * np.ones(n)
    left = sig * np.cos(pan * np.pi / 2)
    right = sig * np.sin(pan * np.pi / 2)
    return left, right


def sand_texture(dur, fps, meta):
    """Textura de arena continua: ruido filtrado cuya intensidad sigue el
    pulso 'speed' de cada nota, en vez de una sola rafaga fija."""
    n = int(dur * SR)
    t_audio = np.arange(n) / SR
    events = meta["events"]
    t_frames_ev = np.linspace(0, dur, len(events))
    spd_arr = np.array([e.get("speed", 0.0) for e in events])
    spd_aud = np.interp(t_audio, t_frames_ev, spd_arr)

    smooth_len = max(1, int(SR * 0.04))
    window = np.ones(smooth_len) / smooth_len
    spd_smooth = np.convolve(spd_aud, window, mode='same')

    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n)
    bright = np.diff(noise, prepend=noise[0])
    tex = noise * 0.5 + bright * 0.5

    amp = 0.025 + 0.55 * (spd_smooth ** 1.5)
    sig = tex * amp

    pan = 0.5 * np.ones(n)
    left = sig * np.cos(pan * np.pi / 2)
    right = sig * np.sin(pan * np.pi / 2)
    return left, right


def dynamic_lead(dur, fps, attractor="lorenz", meta=None):
    N_part = 1000
    FPS = fps
    frames = int(dur * FPS)
    rng = np.random.default_rng(42)

    if attractor == "reaction_diffusion":
        n = int(dur * SR)
        t_audio = np.arange(n) / SR
        events = meta["events"]
        frames_events = len(events)
        t_frames_ev = np.linspace(0, dur, frames_events)
        
        b_arr = np.array([e.get("B_total", 0.0) for e in events])
        b_aud = np.interp(t_audio, t_frames_ev, b_arr)
        
        # Deep drone frequency (C2)
        base_freq = 65.41
        
        # B_total drives the modulation index
        b_norm = np.clip(b_aud / 30000.0, 0.0, 1.0)
        
        phase = np.cumsum(np.full(n, base_freq)) / SR * 2 * np.pi
        mod_phase = np.cumsum(np.full(n, base_freq * 2.0)) / SR * 2 * np.pi
        
        modulator = np.sin(mod_phase) * b_norm * 2.0
        sig = np.sin(phase + modulator)
        
        # Sub bass
        sig += 0.5 * np.sin(phase * 0.5)
        
        env = np.ones(n)
        fade = int(min(0.6, dur / 4) * SR)
        env[:fade] = np.linspace(0, 1, fade) ** 2
        env[-fade:] = np.linspace(1, 0, fade) ** 2
        sig *= env * 0.6
        
        pan = 0.5 + 0.3 * np.sin(np.linspace(0, 10, n))
        left = sig * np.cos(pan * np.pi / 2)
        right = sig * np.sin(pan * np.pi / 2)
        
        return left, right

    if attractor == "chladni":
        n = int(dur * SR)
        t_audio = np.arange(n) / SR
        events = meta["events"]
        frames_events = len(events)
        t_frames_ev = np.linspace(0, dur, frames_events)
        
        m_arr = np.array([e.get("m", 1.0) for e in events])
        n_arr = np.array([e.get("n", 1.0) for e in events])
        spd_arr = np.array([e.get("speed", 0.0) for e in events])
        
        m_aud = np.interp(t_audio, t_frames_ev, m_arr)
        n_aud = np.interp(t_audio, t_frames_ev, n_arr)
        spd_aud = np.interp(t_audio, t_frames_ev, spd_arr)
        
        # Freq proportional to m^2 + n^2
        raw_f_mod = 55.0 * (m_aud**2 + n_aud**2) / 2.0
        
        smooth_len = int(SR * 0.05)
        window = np.ones(smooth_len) / smooth_len
        f_mod = np.convolve(raw_f_mod, window, mode='same')
        
        brightness = np.clip(spd_aud / 2.0, 0.0, 1.0)
        pan = 0.5 * np.ones(n) # Center
        
        phase = np.cumsum(f_mod) / SR * 2 * np.pi
        
        # Singing bowl / Pure resonating glass sound (the melody)
        sig = 1.0 * np.sin(phase)
        sig += 0.4 * np.sin(phase * 2) * brightness
        sig += 0.2 * np.sin(phase * 3) * (brightness**2)
        sig += 0.1 * np.sin(phase * 4) * (brightness**3)
        
        # Deep penetrating cinematic bass pad (Hans Zimmer style)
        t_pad = np.arange(n) / SR
        pad_freqs = [65.41, 98.00, 32.70] # C2, G2, C1
        pad_sig = np.zeros(n)
        for i, f_pad in enumerate(pad_freqs):
            # Slow LFO for movement
            lfo = 1.0 + 0.15 * np.sin(2 * np.pi * (0.05 + 0.01 * i) * t_pad)
            pad_sig += lfo * np.sin(2 * np.pi * f_pad * t_pad)
            # Warmth/saw-ish harmonics
            pad_sig += 0.8 * lfo * np.sin(2 * np.pi * f_pad * 2 * t_pad)
            pad_sig += 0.4 * lfo * np.sin(2 * np.pi * f_pad * 3 * t_pad)
            
        pad_sig *= 0.8 # MAKE IT LOUD AND PENETRATING
        
        # Mix the melodic bowl with the deep bass pad
        sig = sig * 0.4 + pad_sig
        
        env = np.ones(n)
        fade = int(min(0.6, dur / 4) * SR)
        env[:fade] = np.linspace(0, 1, fade) ** 2
        env[-fade:] = np.linspace(1, 0, fade) ** 2
        sig *= env * 0.5
        
        left = sig * np.cos(pan * np.pi / 2)
        right = sig * np.sin(pan * np.pi / 2)

        return left, right

    if attractor == "lorenz":
        SPEED = 0.4
        DT = SPEED / FPS
        SIGMA, RHO, BETA = 10.0, 28.0, 8.0/3.0
        SCALE, OFFSET_Z = 0.15, -25.0
        P0 = np.array([1.0, 1.0, 20.0]) * SCALE
        P0[2] += OFFSET_Z * SCALE
        SEED_RADIUS = 0.1
        
        def vel(p):
            pr = p / SCALE
            pr[:, 2] -= OFFSET_Z
            x, y, z = pr[:, 0], pr[:, 1], pr[:, 2]
            dx = SIGMA * (y - x)
            dy = x * (RHO - z) - y
            dz = x * y - BETA * z
            return np.stack([dx, dy, dz], axis=1) * SCALE
            
    elif attractor == "rossler":
        SPEED = 0.6
        DT = SPEED / FPS
        A, B, C = 0.2, 0.2, 5.7
        SCALE, OFFSET_Z = 0.25, 0.0
        P0 = np.array([10.0, 0.0, 0.0]) * SCALE
        P0[2] += OFFSET_Z * SCALE
        SEED_RADIUS = 0.01 * SCALE
        
        def vel(p):
            pr = p / SCALE
            pr[:, 2] -= OFFSET_Z
            x, y, z = pr[:, 0], pr[:, 1], pr[:, 2]
            dx = -y - z
            dy = x + A * y
            dz = B + z * (x - C)
            return np.stack([dx, dy, dz], axis=1) * SCALE

    elif attractor == "thomas":
        SPEED = 0.5
        DT = SPEED / FPS
        B_val = 0.208186
        SCALE, OFFSET_Z = 0.5, 0.0
        P0 = np.array([1.0, 1.0, 1.0]) * SCALE
        SEED_RADIUS = 0.1 * SCALE
        
        def vel(p):
            pr = p / SCALE
            pr[:, 2] -= OFFSET_Z
            x, y, z = pr[:, 0], pr[:, 1], pr[:, 2]
            dx = np.sin(y) - B_val * x
            dy = np.sin(z) - B_val * y
            dz = np.sin(x) - B_val * z
            return np.stack([dx, dy, dz], axis=1) * SCALE

    elif attractor == "gravity":
        SPEED = 1.0
        DT = SPEED / FPS
        SCALE, OFFSET_Z = 0.5, 0.0
        M_pos = np.array([[5.0, 5.0, 0.0], [-5.0, 5.0, 0.0], [0.0, -5.0, 0.0]]) * SCALE
        M_mass = np.array([150.0, 150.0, 150.0]) * SCALE
        P0 = np.array([0.0, 0.0, 5.0]) * SCALE
        SEED_RADIUS = 2.0 * SCALE
        
        def vel(p):
            pos = p[:, :3] / SCALE
            v = p[:, 3:] / SCALE
            acc = np.zeros_like(pos)
            for j in range(3):
                r_vec = (M_pos[j] / SCALE) - pos
                r_sq = np.sum(r_vec**2, axis=1, keepdims=True)
                r_mag = np.sqrt(r_sq + 1.0) # softening
                acc += (M_mass[j] / SCALE / (r_mag**3)) * r_vec
            acc -= 0.1 * v # friccion
            return np.concatenate([v, acc], axis=1) * SCALE

    # --- PENDULUM: simulación completamente separada ---
    if attractor == "pendulum":
        SPEED = 1.0
        DT = SPEED / FPS
        SCALE, OFFSET_Z = 1.0, 0.0
        G_ACC = 9.81
        SUBSTEPS_P = 2
        DT_SUB = DT / SUBSTEPS_P

        S = np.zeros((N_part, 4), dtype=np.float64)
        S[:, 0] = 3 * np.pi / 4
        S[:, 1] = 3 * np.pi / 4 + rng.normal(0, 1e-3, N_part)

        def pend_deriv(s):
            t1, t2, w1, w2 = s[:, 0], s[:, 1], s[:, 2], s[:, 3]
            d = t1 - t2
            den = 3.0 - np.cos(2 * d)
            a1 = (-3 * G_ACC * np.sin(t1) - G_ACC * np.sin(t1 - 2*t2)
                  - 2 * np.sin(d) * (w2**2 + w1**2 * np.cos(d))) / den
            a2 = (2 * np.sin(d) * (2*w1**2 + 2*G_ACC*np.cos(t1)
                  + w2**2 * np.cos(d))) / den
            return np.stack([w1, w2, a1, a2], axis=1)

        def pend_rk4(s, dt):
            k1 = pend_deriv(s)
            k2 = pend_deriv(s + 0.5*dt*k1)
            k3 = pend_deriv(s + 0.5*dt*k2)
            k4 = pend_deriv(s + dt*k3)
            return s + (dt/6)*(k1 + 2*k2 + 2*k3 + k4)

        com_traj = np.zeros((frames, 3))
        for f in range(frames):
            t1, t2 = S[:, 0], S[:, 1]
            tip_x = np.sin(t1) + np.sin(t2)
            tip_y = -np.cos(t1) - np.cos(t2)
            com_traj[f] = [np.mean(tip_x), 0, np.mean(tip_y)]
            for _ in range(SUBSTEPS_P):
                S = pend_rk4(S, DT_SUB)
    elif attractor == "curl":
        # Curl noise simulation for audio
        SPEED_C = 0.35
        DT = SPEED_C / FPS
        SCALE, OFFSET_Z = 1.0, 0.0
        NOISE_FREQ = 0.6
        TIME_SPEED = 0.15

        def curl_psi(x, y, z, t_val, comp=0):
            s = comp * 17.31 + 31.7
            return (np.sin((x * NOISE_FREQ + t_val * TIME_SPEED) + s)
                    * np.cos((y * NOISE_FREQ + t_val * TIME_SPEED * 0.7) * 1.3 + s * 0.37)
                    * np.sin((z * NOISE_FREQ + t_val * TIME_SPEED * 0.5) * 0.9 + s * 0.71)
                    + 0.5 * np.sin((x * NOISE_FREQ * 1.7 + y * NOISE_FREQ * 0.9 + t_val * TIME_SPEED * 1.3) + s * 1.13)
                          * np.cos((z * NOISE_FREQ * 1.4 + t_val * TIME_SPEED * 0.3) + s * 0.53))

        def curl_vel(pos, t_val):
            x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
            e = 0.01
            vx = ((curl_psi(x, y+e, z, t_val, 2) - curl_psi(x, y-e, z, t_val, 2))
                - (curl_psi(x, y, z+e, t_val, 1) - curl_psi(x, y, z-e, t_val, 1))) / (2*e)
            vy = ((curl_psi(x, y, z+e, t_val, 0) - curl_psi(x, y, z-e, t_val, 0))
                - (curl_psi(x+e, y, z, t_val, 2) - curl_psi(x-e, y, z, t_val, 2))) / (2*e)
            vz = ((curl_psi(x+e, y, z, t_val, 1) - curl_psi(x-e, y, z, t_val, 1))
                - (curl_psi(x, y+e, z, t_val, 0) - curl_psi(x, y-e, z, t_val, 0))) / (2*e)
            return np.stack([vx, vy, vz], axis=1)

        P_curl = rng.normal(0, 0.8, (N_part, 3))
        com_traj = np.zeros((frames, 3))
        for f in range(frames):
            t_val = f * DT
            com_traj[f] = np.nanmean(P_curl, axis=0)
            v = curl_vel(P_curl, t_val)
            P_curl = P_curl + DT * v
            dist = np.sqrt(np.sum(P_curl**2, axis=1))
            mask = dist > 4.0
            if np.any(mask):
                P_curl[mask] *= (4.0 / dist[mask, np.newaxis]) * 0.95
    elif attractor == "tokamak":
        SPEED_TOK = 0.5
        DT = SPEED_TOK / FPS
        SCALE, OFFSET_Z = 1.0, 0.0
        R0 = 3.0
        def tok_vel(pos):
            x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
            rho = np.sqrt(x**2 + y**2) + 1e-5
            phi_x, phi_y, phi_z = -y/rho, x/rho, np.zeros_like(x)
            r_core_x, r_core_y, r_core_z = x*(1-R0/rho), y*(1-R0/rho), z
            pol_x = phi_y * r_core_z - phi_z * r_core_y
            pol_y = phi_z * r_core_x - phi_x * r_core_z
            pol_z = phi_x * r_core_y - phi_y * r_core_x
            pol_mag = np.sqrt(pol_x**2 + pol_y**2 + pol_z**2) + 1e-5
            vx = 1.0 * phi_x + 0.3 * pol_x/pol_mag
            vy = 1.0 * phi_y + 0.3 * pol_y/pol_mag
            vz = 1.0 * phi_z + 0.3 * pol_z/pol_mag
            return np.stack([vx, vy, vz], axis=1)
        
        P_tok = rng.normal(0, 1.0, (N_part, 3))
        P_tok[:,0] += R0
        com_traj = np.zeros((frames, 3))
        for f in range(frames):
            com_traj[f] = np.nanmean(P_tok, axis=0)
            P_tok = P_tok + DT * tok_vel(P_tok)
    elif attractor == "abc":
        # ABC Flow simulation for audio
        SPEED_ABC = 0.3
        DT = SPEED_ABC / FPS
        SCALE, OFFSET_Z = 1.0, 0.0
        A_P, B_P, C_P = np.sqrt(3), np.sqrt(2), 1.0

        def abc_vel(pos, t_val):
            x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
            A = A_P * (1.0 + 0.1 * np.sin(0.3 * t_val))
            B = B_P * (1.0 + 0.1 * np.cos(0.2 * t_val))
            C = C_P * (1.0 + 0.1 * np.sin(0.15 * t_val))
            vx = A * np.sin(z) + C * np.cos(y)
            vy = B * np.sin(x) + A * np.cos(z)
            vz = C * np.sin(y) + B * np.cos(x)
            return np.stack([vx, vy, vz], axis=1)

        P_abc = rng.uniform(0, 2 * np.pi, (N_part, 3))
        com_traj = np.zeros((frames, 3))
        for f in range(frames):
            com_traj[f] = np.nanmean(P_abc, axis=0)
            v = abc_vel(P_abc, f * DT)
            P_abc = (P_abc + DT * v) % (2 * np.pi)
            
    elif attractor == "aizawa":
        SPEED = 0.05
        DT = SPEED / FPS
        SCALE, OFFSET_Z = 1.0, 0.7
        A = 0.95; B = 0.7; C = 0.6; D = 3.5; E = 0.25; F = 0.1
        def aizawa_vel(pos):
            x, y, z = pos[:, 0], pos[:, 1], pos[:, 2]
            dx = (z - B) * x - D * y
            dy = D * x + (z - B) * y
            dz = C + A * z - (z**3) / 3.0 - (x**2 + y**2) * (1.0 + E * z) + F * z * (x**3)
            return np.stack([dx, dy, dz], axis=1)
            
        P_aizawa = rng.uniform(-0.1, 0.1, (N_part, 3))
        P_aizawa[:, 2] += 1.0
        com_traj = np.zeros((frames, 3))
        for f in range(frames):
            com_traj[f] = np.nanmean(P_aizawa, axis=0)
            P_aizawa = P_aizawa + DT * aizawa_vel(P_aizawa)

    elif attractor == "hopf":
        # Centroide sintético: órbita circular 2π-periódica (mismas fibras)
        DT = 1.0 / FPS
        SCALE, OFFSET_Z = 1.0, 0.0
        t_f = np.arange(frames, dtype=np.float64)
        phase = 2.0 * np.pi * t_f / max(1, frames)
        com_traj = np.stack([
            1.6 * np.cos(phase),
            1.6 * np.sin(phase),
            0.45 * np.sin(2.0 * phase),
        ], axis=1)

    elif attractor == "threebody":
        # Centroide de la coreografía figure-8 (periódico)
        DT = 1.0 / FPS
        SCALE, OFFSET_Z = 1.0, 0.0
        t_f = np.arange(frames, dtype=np.float64)
        phase = 2.0 * np.pi * t_f / max(1, frames)
        # Lemniscata suave como proxy del COM de los tres cuerpos
        com_traj = np.stack([
            0.9 * np.sin(phase),
            0.45 * np.sin(2.0 * phase),
            0.15 * np.cos(phase),
        ], axis=1)

    elif attractor == "clifford":
        DT = 1.0 / FPS
        SCALE, OFFSET_Z = 1.0, 0.0
        t_f = np.arange(frames, dtype=np.float64)
        phase = 2.0 * np.pi * t_f / max(1, frames)
        # Proxy del toro girando en 4D
        com_traj = np.stack([
            1.4 * np.cos(phase),
            1.4 * np.sin(phase) * 0.7,
            0.5 * np.sin(2.0 * phase),
        ], axis=1)

    else:
        # Lorenz, Rossler, Thomas, Gravity: generic path
        def rk4(p):
            k1 = vel(p)
            k2 = vel(p + 0.5 * DT * k1)
            k3 = vel(p + 0.5 * DT * k2)
            k4 = vel(p + DT * k3)
            return p + (DT / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

        if attractor == "gravity":
            P_pos = P0 + rng.normal(size=(N_part, 3)) * SEED_RADIUS
            P_vel = rng.normal(size=(N_part, 3)) * (1.0 * SCALE)
            P = np.concatenate([P_pos, P_vel], axis=1)
        else:
            P = P0 + rng.normal(size=(N_part, 3)) * SEED_RADIUS
        
        com_traj = np.zeros((frames, 3))
    
        for f in range(frames):
            pos = P[:, :3] if P.shape[1] == 6 else P
            com_traj[f] = np.nanmean(pos, axis=0)
            P = rk4(P)
        
    com_real = com_traj / SCALE
    com_real[:, 2] -= OFFSET_Z
    X, Y, Z = com_real[:, 0], com_real[:, 1], com_real[:, 2]
    
    dX = np.gradient(X) / DT
    dY = np.gradient(Y) / DT
    dZ = np.gradient(Z) / DT
    Speed = np.sqrt(dX**2 + dY**2 + dZ**2)
    
    t_frames = np.linspace(0, dur, frames)
    n = int(dur * SR)
    t_audio = np.arange(n) / SR

    X_aud = np.interp(t_audio, t_frames, X)
    Z_aud = np.interp(t_audio, t_frames, Z)
    Spd_aud = np.interp(t_audio, t_frames, Speed)
    
    if attractor == "lorenz":
        f_mod = 130.81 * (1.0 + (Z_aud - 20.0) / 40.0)
        brightness = np.clip(Spd_aud / 150.0, 0.0, 1.0)
        pan = np.clip((X_aud + 20) / 40.0, 0.0, 1.0)
    elif attractor == "rossler":
        f_mod = 130.81 * (1.0 + Z_aud / 10.0)
        brightness = np.clip(Spd_aud / 30.0, 0.0, 1.0)
        pan = np.clip((X_aud + 15) / 30.0, 0.0, 1.0)
    elif attractor == "thomas":
        f_mod = 196.00 * (1.0 + Z_aud / 10.0)
        brightness = np.clip(Spd_aud / 5.0, 0.0, 1.0)
        pan = np.clip((X_aud + 5) / 10.0, 0.0, 1.0)
    elif attractor == "pendulum":
        # Pitch follows vertical swing, quantized to pentatonic scale
        base_freq = 130.81 # C3
        # Pentatonic scale ratios (C, D, E, G, A) over multiple octaves
        ratios = np.array([1.0, 1.122, 1.25, 1.5, 1.681, 2.0, 2.245, 2.5, 3.0, 3.363, 4.0, 4.49, 5.0, 6.0])
        idx_float = (Z_aud + 2.0) * 3.0 
        idx = np.clip(np.round(idx_float), 0, len(ratios) - 1).astype(int)
        raw_f_mod = base_freq * ratios[idx]
        
        # Smooth portamento to avoid clicks
        smooth_len = int(SR * 0.05)
        window = np.ones(smooth_len) / smooth_len
        f_mod = np.convolve(raw_f_mod, window, mode='same')
        
        brightness = np.clip(Spd_aud / 8.0, 0.0, 1.0)
        pan = np.clip((X_aud + 2.0) / 4.0, 0.0, 1.0)
    elif attractor == "curl":
        # Pentatonic arpeggio driven by flow speed
        base_freq = 196.00 # G3
        ratios = np.array([1.0, 1.122, 1.25, 1.5, 1.681, 2.0, 2.245, 2.5, 3.0, 3.363, 4.0, 4.49, 5.0, 6.0])
        idx_float = Spd_aud * 2.0
        idx = np.clip(np.round(idx_float), 0, len(ratios) - 1).astype(int)
        raw_f_mod = base_freq * ratios[idx]
        
        smooth_len = int(SR * 0.08)  # Longer portamento for organic feel
        window = np.ones(smooth_len) / smooth_len
        f_mod = np.convolve(raw_f_mod, window, mode='same')
        
        brightness = np.clip(Spd_aud / 5.0, 0.0, 1.0)
        pan = np.clip((X_aud + 3.0) / 6.0, 0.0, 1.0)
    elif attractor == "tokamak":
        # Tokamak drone logic
        base_freq = 130.81 # C3
        ratios = np.array([1.0, 1.122, 1.25, 1.5, 1.681, 2.0, 2.245])
        idx_float = Spd_aud * 3.0
        idx = np.clip(np.round(idx_float), 0, len(ratios) - 1).astype(int)
        raw_f_mod = base_freq * ratios[idx]
        
        smooth_len = int(SR * 0.05)
        window = np.ones(smooth_len) / smooth_len
        f_mod = np.convolve(raw_f_mod, window, mode='same')
        
        brightness = np.clip(Spd_aud / 4.0, 0.0, 1.0)
        pan = np.clip((X_aud + 3.0) / 6.0, 0.0, 1.0)
    elif attractor == "abc":
        # Ethereal arpeggio driven by flow topology
        base_freq = 220.0  # A3
        ratios = np.array([1.0, 1.122, 1.25, 1.5, 1.681, 2.0, 2.245, 2.5, 3.0, 3.363, 4.0, 4.49, 5.0, 6.0])
        idx_float = Spd_aud * 3.0
        idx = np.clip(np.round(idx_float), 0, len(ratios) - 1).astype(int)
        raw_f_mod = base_freq * ratios[idx]
        
        smooth_len = int(SR * 0.06)
        window = np.ones(smooth_len) / smooth_len
        f_mod = np.convolve(raw_f_mod, window, mode='same')
        
        brightness = np.clip(Spd_aud / 4.0, 0.0, 1.0)
        pan = np.clip((X_aud + 3.5) / 7.0, 0.0, 1.0)
    elif attractor == "hopf":
        # Pad cristalino: pitch suave ligado a la órbita de las fibras
        base_freq = 196.00  # G3
        ratios = np.array([1.0, 1.122, 1.25, 1.5, 1.681, 2.0, 2.245, 2.5, 3.0])
        idx_float = (Z_aud + 1.0) * 2.5 + Spd_aud * 0.8
        idx = np.clip(np.round(idx_float), 0, len(ratios) - 1).astype(int)
        raw_f_mod = base_freq * ratios[idx]

        smooth_len = int(SR * 0.1)
        window = np.ones(smooth_len) / smooth_len
        f_mod = np.convolve(raw_f_mod, window, mode="same")

        brightness = np.clip(0.35 + Spd_aud / 6.0, 0.0, 1.0)
        pan = np.clip((X_aud + 2.5) / 5.0, 0.0, 1.0)
    elif attractor == "threebody":
        base_freq = 164.81  # E3
        ratios = np.array([1.0, 1.122, 1.25, 1.5, 1.681, 2.0, 2.245, 2.5, 3.0])
        idx_float = (Z_aud + 1.0) * 2.0 + Spd_aud * 1.2
        idx = np.clip(np.round(idx_float), 0, len(ratios) - 1).astype(int)
        raw_f_mod = base_freq * ratios[idx]

        smooth_len = int(SR * 0.08)
        window = np.ones(smooth_len) / smooth_len
        f_mod = np.convolve(raw_f_mod, window, mode="same")

        brightness = np.clip(0.4 + Spd_aud / 5.0, 0.0, 1.0)
        pan = np.clip((X_aud + 1.5) / 3.0, 0.0, 1.0)
    elif attractor == "clifford":
        base_freq = 174.61  # F3
        ratios = np.array([1.0, 1.122, 1.25, 1.5, 1.681, 2.0, 2.245, 2.5, 3.0])
        idx_float = (Z_aud + 1.0) * 2.2 + Spd_aud * 0.9
        idx = np.clip(np.round(idx_float), 0, len(ratios) - 1).astype(int)
        raw_f_mod = base_freq * ratios[idx]

        smooth_len = int(SR * 0.09)
        window = np.ones(smooth_len) / smooth_len
        f_mod = np.convolve(raw_f_mod, window, mode="same")

        brightness = np.clip(0.35 + Spd_aud / 5.5, 0.0, 1.0)
        pan = np.clip((X_aud + 2.0) / 4.0, 0.0, 1.0)
    else: # gravity
        f_mod = 65.41 * (1.0 + Spd_aud / 20.0) # Speed modulates pitch deeply
        brightness = np.clip(Spd_aud / 15.0, 0.0, 1.0)
        pan = np.clip((X_aud + 10) / 20.0, 0.0, 1.0)

    phase = np.cumsum(f_mod) / SR * 2 * np.pi
    
    sig = np.sin(phase)
    sig += np.sin(phase * 2) * brightness * 0.4
    sig += np.sin(phase * 3) * (brightness**2) * 0.2
    
    env = np.ones(n)
    fade = int(min(0.6, dur / 4) * SR)
    env[:fade] = np.linspace(0, 1, fade) ** 2
    env[-fade:] = np.linspace(1, 0, fade) ** 2
    sig *= env * 0.5
    
    left = sig * np.cos(pan * np.pi / 2)
    right = sig * np.sin(pan * np.pi / 2)
    
    return left, right


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True, help="Path to events.json")
    ap.add_argument("--outdir", required=True, help="Output directory")
    ap.add_argument("--attractor", type=str, choices=["lorenz", "rossler", "gravity", "thomas", "pendulum", "curl", "chladni", "reaction_diffusion", "chladni_melody", "abc", "tokamak", "aizawa", "hopf", "threebody", "clifford", "galactic_spiral"], default="lorenz")
    a = ap.parse_args()

    with open(a.events, encoding="utf-8") as fh:
        meta = json.load(fh)
    dur = meta["duration_s"]
    fps = meta.get("fps", 60)
    n = int(dur * SR)
    os.makedirs(a.outdir, exist_ok=True)

    dl_pad, dr_pad = drone(dur)
    
    if a.attractor == "chladni_melody":
        dl_dyn, dr_dyn = bass_melody(dur, n_segments=15)
    else:
        dl_dyn, dr_dyn = dynamic_lead(dur, fps, a.attractor, meta=meta)

    if a.attractor in ["abc", "tokamak"]:
        dl_dyn = np.zeros_like(dl_pad)
        dr_dyn = np.zeros_like(dr_pad)

    dl = dl_pad * 0.4 + dl_dyn * 0.8
    dr = dr_pad * 0.4 + dr_dyn * 0.8

    hl = np.zeros(n)
    hr = np.zeros(n)
    if a.attractor == "chladni_melody":
        for ev in meta["events"]:
            m = ev.get("m", 1)
            n_val = ev.get("n", 1)
            speed = ev.get("speed", 0.0)
            if speed > 0.95:  # Trigger at the start of the note
                hz = 55.0 * (m**2 + n_val**2) / 2.0
                h = eerie_bell(hz, gain=1.1, dur_tail=4.0)

                start = int((ev.get("frame", 0) / fps) * SR)
                end = min(start + len(h), n)
                hl[start:end] += h[: end - start]
                hr[start:end] += h[: end - start]

        sl, sr_ = sand_texture(dur, fps, meta)
        hl += sl
        hr += sr_
    elif a.attractor not in ["chladni", "reaction_diffusion", "abc", "tokamak"]:
        for ev in meta["events"]:
            hz = NOTE.get(resolve_note(ev), NOTE["C2"])
            h = hit(hz, gain=float(ev.get("intensity", 1.0)), attractor=a.attractor)
            start = int(ev.get("t_seconds", 0.0) * SR)
            end = min(start + len(h), n)
            hl[start:end] += h[: end - start]
            hr[start:end] += h[: end - start]

    write_wav_stereo(os.path.join(a.outdir, "drone.wav"), dl, dr)
    write_wav_stereo(os.path.join(a.outdir, "hits.wav"), hl, hr)
    print(f"[audio] drone.wav + hits.wav  ({dur}s) -> {a.outdir}")


if __name__ == "__main__":
    main()
