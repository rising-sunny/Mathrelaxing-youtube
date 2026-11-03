import argparse,json,subprocess,sys,textwrap
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy.ndimage import gaussian_filter

HERE=Path(__file__).resolve().parent

def image_frames(entry,w,h,count):
    family=entry['family']; p=entry['recipe']['parameters']; rng=np.random.default_rng(entry['recipe']['seed'])
    y,x=np.mgrid[-1.4:1.4:complex(h),-.7875:.7875:complex(w)]
    if family=='waves':
        sources=p.get('sources')
        if sources is None:
            angles=np.arange(p['source_ring_count'])*2*np.pi/p['source_ring_count']
            sources=np.column_stack((np.cos(angles),np.sin(angles)))*p['source_ring_radius']
        distances=[np.hypot(x-a,y-b) for a,b in sources]
    if family=='attractor':
        points=rng.normal(0,.25,(6000,3))+(1 if p['system']=='lorenz' else 0)
        dt=.008 if p['system']=='lorenz' else .04
        def velocity(q):
            X,Y,Z=q.T
            if p['system']=='lorenz': return np.column_stack((p['sigma']*(Y-X),X*(p['rho']-Z)-Y,X*Y-p['beta']*Z))
            return np.column_stack((np.sin(Y)-p['b']*X,np.sin(Z)-p['b']*Y,np.sin(X)-p['b']*Z))
        def step(q):
            k1=velocity(q);k2=velocity(q+dt*k1/2);k3=velocity(q+dt*k2/2);k4=velocity(q+dt*k3)
            return q+dt*(k1+2*k2+2*k3+k4)/6
        for _ in range(1600): points=step(points)
        history=np.zeros((h,w),dtype=float)
    for frame in range(count):
        progress=frame/max(count-1,1)
        if family=='julia':
            c=p['radius']*np.exp(1j*(2*np.pi*progress+p['phase']))
            z=(x+1j*y)*(p['zoom']/1.4); active=np.ones(z.shape,dtype=bool); field=np.zeros(z.shape)
            for iteration in range(180):
                z[active]=z[active]**2+c
                escaped=active & (np.abs(z)>4)
                field[escaped]=(iteration+1)/180
                active[escaped]=False
                if not active.any(): break
            field=np.power(field,.35)
        elif family=='waves':
            t=progress*entry['recipe']['duration_seconds']
            phase=p.get('phase',0)
            if 'phase_end' in p: phase=p['phase_start']+(p['phase_end']-p['phase_start'])*progress
            field=sum(np.sin(p['k']*r-p['omega']*t+(phase if j%2 else 0)) for j,r in enumerate(distances))/len(distances)
            field=(field+1)/2
        elif family=='lissajous':
            canvas=Image.new('L',(w,h)); draw=ImageDraw.Draw(canvas)
            t=np.linspace(0,2*np.pi,3000); delta=p['phase_start']+(p['phase_end']-p['phase_start'])*progress
            X=np.sin(p['a']*t+delta); Y=np.sin(p['b']*t)
            coords=list(zip(w/2+X*w*.41,h*.48-Y*w*.41))
            draw.line(coords,fill=220,width=max(1,w//180))
            field=np.asarray(canvas,dtype=float)/255
            field+=gaussian_filter(field,2)*.4
        elif family=='attractor':
            for _ in range(4): points=step(points)
            assert np.isfinite(points).all()
            angle=np.deg2rad(p['camera_azimuth']); X=points[:,0]*np.cos(angle)+points[:,1]*np.sin(angle)
            Y=points[:,2]-(25 if p['system']=='lorenz' else 0)
            scale=w/(60 if p['system']=='lorenz' else 8)
            px=(w/2+X*scale).astype(int);py=(h*.48-Y*scale).astype(int)
            mask=(px>=0)&(px<w)&(py>=0)&(py<h)
            history*=.94
            history+=np.bincount(py[mask]*w+px[mask],minlength=h*w).reshape(h,w)*.11
            field=1-np.exp(-history)
        else: raise ValueError('Unknown family')
        field=np.clip(field,0,1)
        rgb=np.zeros((h,w,3));rgb[:]=[.012,.018,.04]
        rgb+=field[:,:,None]*np.array([.14,.68,.85])
        rgb+=(field**4)[:,:,None]*np.array([.82,.17,.02])
        yield Image.fromarray((np.clip(rgb,0,1)*255).astype('uint8'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--recipe',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    entry=json.loads(a.recipe.read_text())
    if entry['family']=='cymatics':
        cmd=[sys.executable,str(HERE/'cymatics.py'),'--recipe',str(a.recipe),'--music-generator',str(HERE/'melodic_ambient.py'),'--out',str(a.out)]
        if a.smoke: cmd+=['--preview']
        subprocess.run(cmd,check=True);return
    if a.out.exists(): ap.error('Output directory exists')
    a.out.mkdir(parents=True)
    duration=entry['recipe']['duration_seconds']; fps=2 if a.smoke else 30; count=duration*fps
    w,h=(270,480) if a.smoke else (540,960)
    output_size=(270,480) if a.smoke else (1080,1920)
    music=a.out/'music.wav'
    subprocess.run([sys.executable,str(HERE/'melodic_ambient.py'),'--seed',str(entry['recipe']['audio']['seed']),'--duration',str(duration),'--out',str(music)],check=True)
    W,H=output_size
    fonts='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    titlefont=ImageFont.truetype(fonts,round(W*.045)); small=ImageFont.truetype(fonts,round(W*.028))
    video=a.out/'short.mp4'
    proc=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(fps),'-i','pipe:0','-i',str(music),'-c:v','libx264','-threads','2','-preset','fast','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t',str(duration),'-movflags','+faststart',str(video)],stdin=subprocess.PIPE)
    brightness=[]
    try:
        for i,image in enumerate(image_frames(entry,w,h,count)):
            brightness.append(float(np.asarray(image).std()))
            image=image.resize(output_size,Image.Resampling.LANCZOS);draw=ImageDraw.Draw(image)
            # Opaque header/footer keep text readable over waves and fractals.
            draw.rectangle((0,0,W,H*.22),fill='#03040a');draw.rectangle((0,H*.76,W,H),fill='#03040a')
            title=entry['metadata']['title'].split('|')[0].strip()
            for j,line in enumerate(textwrap.wrap(title.upper(),width=29)):
                draw.text((W/2,H*(.09+j*.035)),line,font=titlefont,fill='#fff1cf',anchor='mm')
            draw.text((W/2,H*.80),'MATHEMATICS IN MOTION',font=small,fill='#fff1cf',anchor='mm')
            draw.text((W/2,H*.85),'SUBSCRIBE FOR MORE MATH',font=small,fill='#fff1cf',anchor='mm')
            draw.text((W/2,H*.90),'@MathRelaxing',font=small,fill='#aab4c4',anchor='mm')
            proc.stdin.write(image.tobytes())
            if i==count//2:image.save(a.out/'cover.jpg')
        proc.stdin.close()
        if proc.wait()!=0:raise RuntimeError('Encoding failed')
    finally:
        if proc.poll() is None:proc.terminate();proc.wait()
    if max(brightness)<1:raise RuntimeError('Empty visual')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(video),'-f','null','-'],check=True)
    (a.out/'validation.json').write_text(json.dumps({'preview':a.smoke,'frames':count,'fps':fps,'width':W,'height':H,'full_decode_passed':True,'internal_resolution':[w,h]}))
    print('Ready:',video)
if __name__=='__main__':main()
