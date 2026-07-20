import os
import subprocess

outdir = r"C:\dev\MathRelaxing-videos-music\output\abc_loop_preview"

tracks = [
    r"C:\Users\sunse\Downloads\ES_Betawaves for Concentration (Short Version) - Joseph Beg.wav",
    r"C:\Users\sunse\Downloads\ES_Enlightened Drift - Amber Glow.wav",
    r"C:\Users\sunse\Downloads\ES_A New Beginning (Theta Drone L216Hz R220Hz) - Bruce Brus.wav",
    r"C:\Users\sunse\Downloads\ES_How Did We Get Here - Hanna Lindgren.wav",
    r"C:\Users\sunse\Downloads\ES_Pillow Magic - Valante.wav"
]

drone_path = os.path.join(outdir, "drone.wav")

def build_audio():
    print("Building FFmpeg filter for 1 hour audio...")
    
    # We need about 3600 seconds. The 5 tracks total ~1555s. 
    # So we loop the playlist 3 times to get ~4665s, then we'll -t 3600.
    playlist = tracks * 3
    
    # Inputs list for ffmpeg
    cmd = ["ffmpeg", "-y"]
    for t in playlist:
        cmd.extend(["-i", t])
        
    cmd.extend(["-stream_loop", "-1", "-i", drone_path])
    
    drone_idx = len(playlist)
    
    # Filter complex
    filter_parts = []
    
    # Normalize all tracks to the same sample rate to avoid acrossfade issues
    for i in range(len(playlist)):
        filter_parts.append(f"[{i}:a]aresample=48000[a{i}];")
        
    # Cascade acrossfades
    fade_duration = 5
    current_out = "[a0]"
    
    for i in range(1, len(playlist)):
        next_in = f"[a{i}]"
        out_name = f"[mix{i}]"
        filter_parts.append(f"{current_out}{next_in}acrossfade=d={fade_duration}:c1=tri:c2=tri{out_name};")
        current_out = out_name
        
    music_mix = current_out
    
    # Mix with drone (drone is input `drone_idx`)
    filter_parts.append(f"[{drone_idx}:a]aresample=48000,volume=0.5[drone_vol];")
    final_out = "[final_audio]"
    filter_parts.append(f"{music_mix}[drone_vol]amix=inputs=2:duration=first:weights=1 1[mixed];")
    
    # Limiter to prevent clipping
    filter_parts.append(f"[mixed]alimiter=limit=0.95{final_out}")
    
    filter_complex = " ".join(filter_parts)
    
    out_audio = os.path.join(outdir, "audio_1h_mix.aac")
    
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", final_out,
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", "3600",
        out_audio
    ])
    
    print("Running FFmpeg for audio...")
    subprocess.run(cmd, check=True)
    return out_audio

def build_video(audio_path):
    print("Building concat list...")
    concat_txt = os.path.join(outdir, "concat.txt")
    
    with open(concat_txt, "w") as f:
        for _ in range(225):
            f.write(f"file 'seamless_preview_fix.mp4'\n")
            
    print("Muxing final video...")
    out_video = os.path.join(outdir, "abc_flow_1h_final.mp4")
    
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
    print("DONE! ->", out_video)

if __name__ == "__main__":
    from _deprecated_1h import guard_1h_format
    guard_1h_format(__file__)

    audio = build_audio()
    build_video(audio)
