import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(REPO, "output", "thomas_1h")

def render_base_clip():
    print("\n[thomas_1h] === PASO 1: Renderizando Clip Base 15s ===")
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", "thomas_1h",
        "--scene", "scenes/thomas_1h_numpy.py",
        "--attractor", "thomas",
        "--engine", "numpy",
        "--frames", "900",
        "--res", "1080",
        "--fps", "60",
        "--format", "16:9"
    ])
    if r.returncode != 0:
        sys.exit("Error en el render base.")
        
def build_1h_audio():
    print("\n[thomas_1h] === PASO 2: Generando Audio de 1 Hora ===")
    tracks = [
        r"C:\Users\sunse\Downloads\ES_Betawaves for Concentration (Short Version) - Joseph Beg.wav",
        r"C:\Users\sunse\Downloads\ES_Enlightened Drift - Amber Glow.wav",
        r"C:\Users\sunse\Downloads\ES_A New Beginning (Theta Drone L216Hz R220Hz) - Bruce Brus.wav",
        r"C:\Users\sunse\Downloads\ES_How Did We Get Here - Hanna Lindgren.wav",
        r"C:\Users\sunse\Downloads\ES_Pillow Magic - Valante.wav"
    ]
    
    # 5 tracks is about ~25 mins. We loop them 3 times.
    playlist = tracks * 3
    
    cmd = ["ffmpeg", "-y"]
    for t in playlist:
        cmd.extend(["-i", t])
        
    drone_path = os.path.join(OUTDIR, "drone.wav")
    hits_path = os.path.join(OUTDIR, "hits.wav")
    
    # We will loop drone and hits
    cmd.extend(["-stream_loop", "-1", "-i", drone_path])
    cmd.extend(["-stream_loop", "-1", "-i", hits_path])
    
    drone_idx = len(playlist)
    hits_idx = len(playlist) + 1
    
    filter_parts = []
    
    for i in range(len(playlist)):
        filter_parts.append(f"[{i}:a]aresample=48000[a{i}];")
        
    # Cascade acrossfades for music
    fade_duration = 5
    current_out = "[a0]"
    for i in range(1, len(playlist)):
        next_in = f"[a{i}]"
        out_name = f"[mix{i}]"
        filter_parts.append(f"{current_out}{next_in}acrossfade=d={fade_duration}:c1=tri:c2=tri{out_name};")
        current_out = out_name
        
    music_mix = current_out
    
    # Ducking logic: Hits should duck the music and drone
    # Sub-mix music and drone first
    filter_parts.append(f"[{drone_idx}:a]aresample=48000,volume=0.3[drone_vol];")
    filter_parts.append(f"{music_mix}[drone_vol]amix=inputs=2:duration=first:weights=1 1[music_drone];")
    
    # Now duck [music_drone] using [hits_idx]
    filter_parts.append(f"[{hits_idx}:a]aresample=48000[hits_clean];")
    filter_parts.append(f"[music_drone][hits_clean]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[ducked_music];")
    
    # Mix ducked music with hits
    filter_parts.append(f"[ducked_music][hits_clean]amix=inputs=2:duration=first:weights=1 1.2:normalize=0[mixed];")
    filter_parts.append(f"[mixed]alimiter=limit=0.95[final_audio]")
    
    filter_complex = " ".join(filter_parts)
    out_audio = os.path.join(OUTDIR, "audio_1h_mix.aac")
    
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[final_audio]",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", "3600",
        out_audio
    ])
    
    print("Running FFmpeg for 1H audio...")
    subprocess.run(cmd, check=True)
    return out_audio

def build_1h_video(audio_path):
    print("\n[thomas_1h] === PASO 3: Ensamblando Video de 1 Hora ===")
    concat_txt = os.path.join(OUTDIR, "concat.txt")
    
    # 15s clip * 240 = 3600s (1 hora)
    with open(concat_txt, "w") as f:
        for _ in range(240):
            f.write(f"file 'video_silent.mp4'\n")
            
    out_video = os.path.join(OUTDIR, "thomas_1h_final.mp4")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "copy",
        "-t", "3600",
        out_video
    ]
    subprocess.run(cmd, check=True)
    print("\n[thomas_1h] DONE! ->", out_video)

if __name__ == "__main__":
    os.makedirs(OUTDIR, exist_ok=True)
    render_base_clip()
    audio_path = build_1h_audio()
    build_1h_video(audio_path)
