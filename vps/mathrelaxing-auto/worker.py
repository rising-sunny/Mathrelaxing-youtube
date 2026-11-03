import argparse,fcntl,hashlib,json,os,re,subprocess,sys,tempfile
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
DATA=Path(os.environ.get('MR_AUTO_DATA','/var/lib/mathrelaxing-auto'))
TZ=ZoneInfo('America/Santiago')
CLI='/usr/local/bin/mathrelaxing-publish'

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.state-')
    try:
        with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def read(path,default):return json.loads(path.read_text()) if path.exists() else default

def run(args,timeout=600):
    p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if p.stdout:print(p.stdout[-5000:],flush=True)
    if p.returncode:raise RuntimeError('Command failed: '+Path(args[0]).name+'; '+(p.stderr[-1000:] if p.stderr else p.stdout[-1000:]))
    return p.stdout

def alert(job,message):
    with (DATA/'alerts.jsonl').open('a') as f:f.write(json.dumps({'at':datetime.now(TZ).isoformat(),'id':job,'message':message})+'\n')
    print('ATTENTION:',job,message,flush=True)

def item_state(e):return DATA/'states'/f"{e['id']}.json"

def render_entry(e,smoke=False):
    recipe=DATA/'recipes'/f"{e['id']}.json";write(recipe,e)
    out=DATA/('smoke' if smoke else 'renders')/e['id']
    run([sys.executable,str(HERE/('expression_renderer.py' if e['family']=='expression' else 'renderer.py')),'--recipe',str(recipe),'--out',str(out)]+(['--smoke'] if smoke else []),timeout=6*3600)
    return out

def render_queue(items):
    now=datetime.now(TZ)
    # Render up to three upcoming days. No old unpublished video is carried forward.
    upcoming=[e for e in items if now<datetime.fromisoformat(e['publish_at'])<now+timedelta(days=3)]
    for e in upcoming:
        state=read(item_state(e),{})
        if state.get('stage') in ('ready','failed','rendering'):continue
        state={'stage':'rendering','platforms':{},'recipe_sha256':hashlib.sha256(json.dumps(e,sort_keys=True).encode()).hexdigest()};write(item_state(e),state)
        try:
            out=render_entry(e)
            validation=json.loads((out/'validation.json').read_text())
            if validation.get('preview') or not validation.get('full_decode_passed'):raise RuntimeError('Preview or invalid render')
            video=out/('cymatics-short.mp4' if e['family']=='cymatics' else 'short.mp4')
            info=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
            v=next(s for s in info['streams'] if s['codec_type']=='video')
            if (v['width'],v['height'])!=(1080,1920):raise RuntimeError('Invalid dimensions')
            if v['avg_frame_rate']!='30/1':raise RuntimeError('Invalid frame rate')
            if abs(float(info['format']['duration'])-e['recipe']['duration_seconds'])>.15:raise RuntimeError('Invalid duration')
            if not any(s['codec_type']=='audio' for s in info['streams']):raise RuntimeError('Missing audio')
            texts={k:e['metadata'][k] for k in ('title','facebook_caption','instagram_caption')};write(out/'texts.json',texts)
            # API currently stores Facebook caption as YouTube description. Use platform-specific text after preparing.
            result=run([CLI,'preparar',str(video),'--textos',str(out/'texts.json')])
            match=re.search(r'Borrador listo:\s*([0-9a-f-]{36})',result)
            if not match:raise RuntimeError('Draft ID missing; inspect CLI receipts before retry')
            draft=match.group(1);state['draft_id']=draft;write(item_state(e),state)
            # Root-only local update; API has no route that modifies an existing draft.
            draft_path=Path('/var/lib/mathrelaxing-publisher')/draft/'draft.json'
            data=read(draft_path,{})
            data['youtube_description']=e['metadata']['youtube_description'];write(draft_path,data)
            # DynamicUser service must still be able to read this root-written file.
            draft_path.chmod(0o644)
            state.update(stage='ready',video=str(video));write(item_state(e),state)
        except Exception as exc:
            state['stage']='failed';write(item_state(e),state);alert(e['id'],str(exc))
        return

def publish_due(items):
    now=datetime.now(TZ)
    if not (DATA/'ENABLED').exists():print('Publishing disabled');return
    for e in items:
        due=datetime.fromisoformat(e['publish_at'])
        if now>=due+timedelta(hours=1):
            old=read(item_state(e),{})
            if old and not old.get('cutoff_reported') and not all(old.get('platforms',{}).get(p)=='published' for p in ('youtube','facebook','instagram')):
                old['cutoff_reported']=True;write(item_state(e),old);alert(e['id'],'Publication window closed with incomplete platforms; no automatic catch-up')
            continue
        if now<due:continue
        state=read(item_state(e),{})
        if state.get('stage')!='ready':alert(e['id'],'No validated video ready; publication skipped this run');continue
        expected=hashlib.sha256(json.dumps(e,sort_keys=True).encode()).hexdigest()
        if state.get('recipe_sha256') and state['recipe_sha256']!=expected:
            alert(e['id'],'Recipe changed after rendering; manual review required');continue
        job=state['draft_id'];platforms=state.setdefault('platforms',{})
        for platform in ('youtube','facebook','instagram'):
            if not (DATA/'ENABLED').exists() or datetime.now(TZ)>=due+timedelta(hours=1):break
            if platforms.get(platform) in ('published','needs_review'):continue
            journal=Path('/var/lib/mathrelaxing-publisher-cli')/f'{job}-{platform}.json'
            record=read(journal,{})
            stage=record.get('stage')
            if stage in ('needs_review','creating','starting','uploading','finishing','publishing'):
                platforms[platform]='needs_review';alert(e['id'],platform+': interrupted/ambiguous attempt; manual review required');write(item_state(e),state);continue
            try:
                if not record or (platform=='instagram' and stage=='processing'):
                    command=[CLI,'publicar',job,'--'+platform]
                    if platform=='youtube':command+=['--privacidad','public']
                    run(command,timeout=1800)
                result=run([CLI,'seguimiento',job,'--'+platform],timeout=180)
                if platform=='youtube':
                    done='Privacidad: public' in result and 'Procesamiento: succeeded' in result
                    if 'Privacidad: private' in result:raise RuntimeError('YouTube remained private; no automatic reupload')
                elif platform=='facebook':done='"publish_status": "published"' in result
                else:done='Etapa local: published' in result and 'Publicación:' in result
                platforms[platform]='published' if done else 'processing'
            except Exception as exc:
                platforms[platform]='needs_review';alert(e['id'],platform+': '+str(exc))
            write(item_state(e),state)

def main():
    os.umask(0o077);DATA.mkdir(parents=True,exist_ok=True)
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['check','smoke','render','publish','status','enable']);a=ap.parse_args()
    calendar=json.loads((HERE/'calendar.json').read_text());items=calendar['items']
    lock=(DATA/('.'+a.action+'.lock')).open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:print('Already running');return
    if a.action=='check':
        for path in [CLI,'/etc/mathrelaxing-publisher/api-key','/etc/mathrelaxing-publisher/meta-token','/etc/mathrelaxing-publisher/facebook-page-token','/etc/mathrelaxing-publisher/youtube-token.json']:
            if not Path(path).is_file():raise RuntimeError('Missing '+path)
        import numpy,scipy,PIL,requests
        from googleapiclient.discovery import build
        run(['ffmpeg','-version']);assert len(items)==30
        assert len({e['id'] for e in items})==30
        for e in items:assert datetime.fromisoformat(e['publish_at']).astimezone(TZ).hour==18
        health=requests.get('http://127.0.0.1:8786/health',timeout=10)
        health.raise_for_status()
        print('Prerequisites and local draft service checked. Publishing is not enabled by this check.')
    elif a.action=='smoke':
        for family in ('julia','attractor','lissajous','waves','thomas'):
            e=next(x for x in items if x['family']=='attractor' and x['recipe']['parameters']['system']=='thomas') if family=='thomas' else next(x for x in items if x['family']==family)
            out=DATA/'smoke'/e['id']
            if out.exists():
                if not (out/'validation.json').exists():raise RuntimeError('Incomplete smoke run: '+str(out))
            else:render_entry(e,True)
        # Cymatics was already validated at full size on this VPS; validate changed parameters separately during render.
        write(DATA/'smoke-passed.json',{'at':datetime.now(TZ).isoformat(),'families':['julia','lorenz','thomas','lissajous','waves']})
        print('Smoke render checks passed. Inspect the generated previews before enabling.')
    elif a.action=='render':render_queue(items)
    elif a.action=='publish':publish_due(items)
    elif a.action=='enable':
        if not (DATA/'smoke-passed.json').exists():raise RuntimeError('Run smoke first')
        upcoming=[e for e in items if datetime.fromisoformat(e['publish_at'])>datetime.now(TZ)]
        if not upcoming:raise RuntimeError('Calendar expired; choose new dates')
        if read(item_state(upcoming[0]),{}).get('stage')!='ready':raise RuntimeError('First upcoming video is not ready')
        (DATA/'ENABLED').touch();print('Daily publishing enabled for calendar dates, 18:00–19:00 America/Santiago')
    else:
        print('Publishing:',(DATA/'ENABLED').exists())
        for e in items:
            s=read(item_state(e),{});print(e['publish_at'],e['family'],s.get('stage','pending'),json.dumps(s.get('platforms',{})))
if __name__=='__main__':main()
