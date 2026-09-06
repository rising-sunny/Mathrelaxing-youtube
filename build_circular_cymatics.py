import os
import subprocess
import sys
import json
import numpy as np
from scipy.io import wavfile

REPO = os.path.dirname(os.path.abspath(__file__))
NAME = "circular_cymatics"

sys.path.insert(0, os.path.join(REPO, "tools"))
from music_library import find_track  # noqa: E402

OUTDIR = os.path.join(REPO, "output", NAME)

def render_video():
    print(f"\n[{NAME}] === PASO 1: Renderizando Partículas (Numpy) ===")
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "scenes", f"{NAME}.py"),
        "--name", NAME,
        "--engine", "numpy",
        "--frames", "900",
        "--res", "1024",
        "--fps", "60",
        "--format", "9:16"
    ])
    if r.returncode != 0:
        sys.exit(f"Error en render_video {NAME}")

def build_audio():
    print(f"\n[{NAME}] === PASO 2: Sintetizando Sonido Resonante ===")
    events_path = os.path.join(REPO, "data", f"{NAME}_events.json")
    with open(events_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    duration = data["duration_s"]
    sample_rate = 48000
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    
    # Sintetizar un pad ambiental con las frecuencias
    audio = np.zeros_like(t)
    
    events = data["events"]
    # Agregar un evento dummy al final
    events.append({"t_seconds": duration, "freq": events[-1]["freq"] if events else 440})
    
    for i in range(len(events) - 1):
        t_start = events[i]["t_seconds"]
        t_end = events[i+1]["t_seconds"]
        freq = events[i]["freq"]
        
        # Crossfade envelope (suave transición)
        idx_start = int(t_start * sample_rate)
        idx_end = int(t_end * sample_rate)
        length = idx_end - idx_start
        
        local_t = t[idx_start:idx_end]
        
        # Osciladores (fundamental + armónicos)
        wave = np.sin(2 * np.pi * freq * local_t) * 0.5
        wave += np.sin(2 * np.pi * freq * 1.5 * local_t) * 0.25 # Quinta
        wave += np.sin(2 * np.pi * freq * 2.0 * local_t) * 0.15 # Octava
        
        # Envelope de ataque y decaimiento
        env = np.ones(length)
        fade_len = int(sample_rate * 0.5) # 0.5 sec crossfade
        
        # Fade in
        if length > fade_len:
            env[:fade_len] = np.linspace(0, 1, fade_len)
            # Fade out
            env[-fade_len:] = np.linspace(1, 0, fade_len)
            
        audio[idx_start:idx_end] += wave * env
        
    # Añadir un "Sub-bajo" constante
    sub_bass = np.sin(2 * np.pi * 55 * t) * 0.3
    audio += sub_bass
    
    # Normalizar
    audio = audio / np.max(np.abs(audio)) * 0.8
    
    audio_path = os.path.join(OUTDIR, f"{NAME}_audio.wav")
    wavfile.write(audio_path, sample_rate, (audio * 32767).astype(np.int16))
    print(f"Audio generado en {audio_path}")
    return audio_path

def mux_video(audio_path):
    print(f"\n[{NAME}] === PASO 3: Ensamblando Video 9:16 Final ===")
    frames_dir = os.path.join(OUTDIR, "frames")
    out_video = os.path.join(OUTDIR, f"{NAME}_final.mp4")
    ambient_track = find_track("enlightened_drift")
    formula_img = os.path.join(OUTDIR, "bessel_formula.png")
    
    cmd = [
        "ffmpeg", "-y",
        "-framerate", "60",
        "-i", os.path.join(frames_dir, "%04d.png"),
        "-i", audio_path,
        "-i", ambient_track,
        "-i", formula_img,
        "-filter_complex", "[0:v][3:v]overlay=(main_w-overlay_w)/2:main_h-overlay_h-120[v];[1:a]volume=0.2[a1];[2:a]volume=1.0[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=2[a]",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        out_video
    ]
    subprocess.run(cmd, check=True)
    print(f"\n[{NAME}] DONE! ->", out_video)

if __name__ == "__main__":
    # render_video() # Ya renderizado
    # audio_path = build_audio() # Ya sintetizado
    audio_path = os.path.join(OUTDIR, f"{NAME}_audio.wav")
    mux_video(audio_path)
