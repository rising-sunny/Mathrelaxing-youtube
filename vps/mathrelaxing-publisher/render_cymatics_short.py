#!/usr/bin/env python3
"""Self-contained cymatics-inspired short. Requires NumPy, SciPy, Pillow, FFmpeg."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import map_coordinates, gaussian_filter
from scipy.special import jv


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--music-generator',type=Path,required=True)
    ap.add_argument('--preview',action='store_true')
    a=ap.parse_args()
    if a.out.exists(): ap.error('Output directory exists; choose a new directory')
    if not a.music_generator.is_file(): ap.error('Music generator not found')
    a.out.mkdir(parents=True)
    w,h=(270,480) if a.preview else (1080,1920)
    fps=30; duration=16; frames=fps*duration
    n=300000; grid=320; extent=1.15
    axis=np.linspace(-extent,extent,grid)
    x,y=np.meshgrid(axis,axis)
    radius=np.hypot(x,y); theta=np.arctan2(y,x)
    modes=[(3,16),(5,19),(7,22)]
    fields=[np.abs(jv(order,k*radius)*np.cos(order*theta)) for order,k in modes]
    gradients=[np.gradient(field,axis[1]-axis[0]) for field in fields]
    rng=np.random.default_rng(20261021)
    def initialize():
        r=np.sqrt(rng.random(n)); angle=rng.random(n)*2*np.pi
        return np.column_stack((r*np.cos(angle),r*np.sin(angle))).astype(np.float32)
    p=initialize()
    def step(mode):
        gy,gx=gradients[mode]
        for _ in range(3):
            coords=((p[:,1]+extent)/(2*extent)*(grid-1),(p[:,0]+extent)/(2*extent)*(grid-1))
            dx=map_coordinates(gx,coords,order=1,mode='nearest')
            dy=map_coordinates(gy,coords,order=1,mode='nearest')
            mag=np.hypot(dx,dy)+.1
            p[:,0]-=.012*dx/mag; p[:,1]-=.012*dy/mag
            p[:]+=rng.normal(0,.0006,p.shape)
            radii=np.hypot(p[:,0],p[:,1]); mask=radii>1
            p[mask]/=radii[mask,None]
    for _ in range(45): step(0)
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if not Path(font_path).exists(): ap.error('Install fonts-dejavu-core')
    title_font=ImageFont.truetype(font_path,round(w*.053))
    small=ImageFont.truetype(font_path,round(w*.028))
    music=a.out/'music.wav'
    subprocess.run([sys.executable,str(a.music_generator),'--duration',str(duration),
                    '--seed','61000','--out',str(music)],check=True)
    video=a.out/'cymatics-short.mp4'
    command=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n',
             '-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(fps),'-i','pipe:0',
             '-i',str(music),'-c:v','libx264','-threads','2','-preset','fast','-crf','20',
             '-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t',str(duration),
             '-movflags','+faststart',str(video)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for f in range(frames):
            t=f/fps; mode=0 if t<5 else (1 if t<10 else 2)
            if f in (150,300): p=initialize()
            step(mode)
            scale=w/2.25
            px=np.clip((p[:,0]*scale+w/2).astype(int),0,w-1)
            py=np.clip((-p[:,1]*scale+h*.48).astype(int),0,h-1)
            count=np.bincount(py*w+px,minlength=w*h).reshape(h,w)
            intensity=1-np.exp(-count*.55)
            glow=gaussian_filter(intensity,1.2)
            rgb=np.zeros((h,w,3)); rgb[:]=[.012,.018,.04]
            rgb+=intensity[:,:,None]*[1,.7,.19]+glow[:,:,None]*[.5,.24,.04]
            im=Image.fromarray((np.clip(rgb,0,1)*255).astype('uint8'))
            draw=ImageDraw.Draw(im)
            def label(y,text,font=small,color='#fff1cf'):
                draw.text((w/2,h*y),text,font=font,fill=color,anchor='mm')
            label(.105,'300,000 GRAINS',title_font)
            label(.15,'ONE PATTERN AT A TIME')
            label(.76,'WATCH THE SAND REARRANGE' if t<12 else 'WHAT SHAPE COMES NEXT?')
            label(.805,'Cymatics-inspired simulation',color='#aab4c4')
            label(.87,'SUBSCRIBE FOR MORE' if t>=13 else '@MathRelaxing')
            process.stdin.write(im.tobytes())
            if f in (90,240,420): im.save(a.out/f'frame-{f}.jpg')
            if f%30==0: print(f'Rendering {f}/{frames}',flush=True)
        process.stdin.close()
        if process.wait()!=0: raise RuntimeError('FFmpeg encoding failed')
    finally:
        if process.poll() is None:
            process.terminate(); process.wait()
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(video),'-f','null','-'],check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
    stream=next(s for s in probe['streams'] if s['codec_type']=='video')
    assert stream['width']==w and stream['height']==h
    assert int(stream['nb_frames'])==frames
    assert abs(float(probe['format']['duration'])-duration)<.1
    metadata={'title':'300,000 Grains Form Stars | Cymatics #Shorts',
              'facebook_caption':'300,000 simulated grains. Three mathematical patterns. Which one is your favorite?\n\nCymatics-inspired computer simulation using Bessel-function fields, not measured physical resonances. Original procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #Cymatics #GenerativeArt',
              'instagram_caption':'300,000 grains. Three patterns. Watch the sand rearrange.\n\nWhich pattern would you watch again?\n\nCymatics-inspired computer simulation. Original procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more.\n\n#MathRelaxing #Cymatics #MathArt #GenerativeArt #CreativeCoding'}
    (a.out/'texts.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (a.out/'validation.json').write_text(json.dumps({'duration':duration,'frames':frames,'width':w,'height':h,'full_decode_passed':True,'preview':a.preview},indent=2)+'\n')
    print('Ready:',video)
    print('Texts:',a.out/'texts.json')
    print('Nothing was published.')

if __name__=='__main__': main()
