import os
import subprocess
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(REPO, "output", "aizawa_1h")

def render_base_clip():
    print("\n[aizawa_1h] === PASO 1: Renderizando Clip Base 15s ===")
    r = subprocess.run([
        sys.executable, os.path.join(REPO, "render", "build_clip.py"),
        "--name", "aizawa_1h",
        "--scene", "scenes/aizawa_1h_numpy.py",
        "--attractor", "aizawa",
        "--engine", "numpy",
        "--frames", "900",
        "--res", "1080",
        "--fps", "60",
        "--format", "16:9"
    ])
    if r.returncode != 0:
        sys.exit("Error en el render base.")
        
def build_1h_audio():
    print("\n[aizawa_1h] === PASO 2: Generando Audio de 1 Hora ===")
    tracks = [
        r"C:\Users\sunse\Downloads\ES_Betawaves for Concentration (Short Version) - Joseph Beg.wav"
    ]
    
    # Track is ~3 mins, loop 25 times
    playlist = tracks * 25
    
    cmd = ["ffmpeg", "-y"]
    for t in playlist:
        cmd.extend(["-i", t])
        
    hits_path = os.path.join(OUTDIR, "hits.wav")
    cmd.extend(["-stream_loop", "-1", "-i", hits_path])
    
    hits_idx = len(playlist)
    filter_parts = []
    
    for i in range(len(playlist)):
        filter_parts.append(f"[{i}:a]aresample=48000[a{i}];")
        
    fade_duration = 10
    current_out = "[a0]"
    for i in range(1, len(playlist)):
        next_in = f"[a{i}]"
        out_name = f"[mix{i}]"
        filter_parts.append(f"{current_out}{next_in}acrossfade=d={fade_duration}:c1=tri:c2=tri{out_name};")
        current_out = out_name
        
    music_mix = current_out
    
    filter_parts.append(f"[{hits_idx}:a]aresample=48000[hits_clean];")
    filter_parts.append(f"{music_mix}[hits_clean]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[ducked_music];")
    filter_parts.append(f"[ducked_music][hits_clean]amix=inputs=2:duration=first:weights=1 1.5:normalize=0[mixed];")
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
    print("\n[aizawa_1h] === PASO 3: Ensamblando Video de 1 Hora ===")
    concat_txt = os.path.join(OUTDIR, "concat.txt")
    
    # 15s clip * 240 = 3600s
    with open(concat_txt, "w") as f:
        for _ in range(240):
            f.write(f"file 'video_silent.mp4'\n")
            
    out_video = os.path.join(OUTDIR, "aizawa_1h_final.mp4")
    
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
    print("\n[aizawa_1h] DONE! ->", out_video)

if __name__ == "__main__":
    from _deprecated_1h import guard_1h_format
    guard_1h_format(__file__)

    os.makedirs(OUTDIR, exist_ok=True)
    render_base_clip()
    audio_path = build_1h_audio()
    build_1h_video(audio_path)
