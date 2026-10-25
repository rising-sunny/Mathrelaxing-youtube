root@ubuntu-4gb-hil-1:~# ls -la /opt/mathrelaxing-auto /opt/mathrelaxing-publisher
git -C /opt/mathrelaxing-auto remote -v; git -C /opt/mathrelaxing-publisher remote -v
grep -nE "def |argv|render|upload|publish|enabled|youtube|tiktok|instagram" /opt/mathrelaxing-auto/worker.py | head -60
grep -rniE "enabled|publish|youtube|tiktok|instagram" /opt/mathrelaxing-auto/*.json /opt/mathrelaxing-publisher/*.json /opt/mathrelaxing-publisher/.env 2>/dev/null | grep -viE "token|secret|key|password"
/opt/mathrelaxing-auto:
total 184
drwxr-xr-x  3 root root   4096 Oct 20 17:17 .
drwxr-xr-x 15 root root   4096 Oct 21 20:10 ..
-rw-r--r--  1 root root 134378 Oct 20 17:17 calendar.json
-rw-r--r--  1 root root   6466 Oct 20 17:17 cymatics.py
-rw-r--r--  1 root root   4367 Oct 20 17:17 melodic_ambient.py
drwxr-xr-x  2 root root   4096 Oct 20 17:17 __pycache__
-rw-r--r--  1 root root   6968 Oct 20 17:17 renderer.py
-rw-r--r--  1 root root   4052 Oct 20 17:17 test_worker.py
-rw-r--r--  1 root root  10147 Oct 20 17:17 worker.py

/opt/mathrelaxing-publisher:
total 80
drwxr-xr-x  5 root root 4096 Oct 22 19:58 .
drwxr-xr-x 15 root root 4096 Oct 21 20:10 ..
-rw-r--r--  1 root root 3944 Oct 20 15:51 app.before-media.py
-rw-r--r--  1 root root 4747 Oct 22 19:58 app.py
-rw-r--r--  1 root root 4736 Oct 20 15:59 app.py.backup.20261022-195801
drwx------  2 root root 4096 Oct 20 15:56 backup.2MIjSL
-rw-r--r--  1 root root 5765 Oct 20 15:58 facebook_reels.py
-rw-r--r--  1 root root 6612 Oct 20 16:02 instagram_reels.py
-rwxr-x---  1 root root 4367 Oct 20 16:43 melodic_ambient.py
drwxr-xr-x  2 root root 4096 Oct 20 16:24 __pycache__
-rwxr-x---  1 root root 6108 Oct 20 16:55 render_cymatics_short.py
drwxr-xr-x  5 root root 4096 Oct 20 15:49 venv
-rw-r--r--  1 root root 5661 Oct 20 16:24 youtube_upload.py
fatal: not a git repository (or any of the parent directories): .git
fatal: not a git repository (or any of the parent directories): .git
9:CLI='/usr/local/bin/mathrelaxing-publish'
11:def write(path,value):
20:def read(path,default):return json.loads(path.read_text()) if path.exists() else default
22:def run(args,timeout=600):
28:def alert(job,message):
32:def item_state(e):return DATA/'states'/f"{e['id']}.json"
34:def render_entry(e,smoke=False):
36:    out=DATA/('smoke' if smoke else 'renders')/e['id']
37:    run([sys.executable,str(HERE/'renderer.py'),'--recipe',str(recipe),'--out',str(out)]+(['--smoke'] if smoke else []),timeout=6*3600)
40:def render_queue(items):
42:    # Render up to three upcoming days. No old unpublished video is carried forward.
43:    upcoming=[e for e in items if now<datetime.fromisoformat(e['publish_at'])<now+timedelta(days=3)]
46:        if state.get('stage') in ('ready','failed','rendering'):continue
47:        state={'stage':'rendering','platforms':{},'recipe_sha256':hashlib.sha256(json.dumps(e,sort_keys=True).encode()).hexdigest()};write(item_state(e),state)
49:            out=render_entry(e)
51:            if validation.get('preview') or not validation.get('full_decode_passed'):raise RuntimeError('Preview or invalid render')
59:            texts={k:e['metadata'][k] for k in ('title','facebook_caption','instagram_caption')};write(out/'texts.json',texts)
66:            draft_path=Path('/var/lib/mathrelaxing-publisher')/draft/'draft.json'
68:            data['youtube_description']=e['metadata']['youtube_description'];write(draft_path,data)
76:def publish_due(items):
80:        due=datetime.fromisoformat(e['publish_at'])
83:            if old and not old.get('cutoff_reported') and not all(old.get('platforms',{}).get(p)=='published' for p in ('youtube','facebook','instagram')):
91:            alert(e['id'],'Recipe changed after rendering; manual review required');continue
93:        for platform in ('youtube','facebook','instagram'):
95:            if platforms.get(platform) in ('published','needs_review'):continue
96:            journal=Path('/var/lib/mathrelaxing-publisher-cli')/f'{job}-{platform}.json'
99:            if stage in ('needs_review','creating','starting','uploading','finishing','publishing'):
102:                if not record or (platform=='instagram' and stage=='processing'):
104:                    if platform=='youtube':command+=['--privacidad','public']
107:                if platform=='youtube':
109:                    if 'Privacidad: private' in result:raise RuntimeError('YouTube remained private; no automatic reupload')
110:                elif platform=='facebook':done='"publish_status": "published"' in result
111:                else:done='Etapa local: published' in result and 'Publicación:' in result
112:                platforms[platform]='published' if done else 'processing'
117:def main():
119:    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['check','smoke','render','publish','status','enable']);a=ap.parse_args()
125:        for path in [CLI,'/etc/mathrelaxing-publisher/api-key','/etc/mathrelaxing-publisher/meta-token','/etc/mathrelaxing-publisher/facebook-page-token','/etc/mathrelaxing-publisher/youtube-token.json']:
131:        for e in items:assert datetime.fromisoformat(e['publish_at']).astimezone(TZ).hour==18
134:        print('Prerequisites and local draft service checked. Publishing is not enabled by this check.')
141:            else:render_entry(e,True)
142:        # Cymatics was already validated at full size on this VPS; validate changed parameters separately during render.
144:        print('Smoke render checks passed. Inspect the generated previews before enabling.')
145:    elif a.action=='render':render_queue(items)
146:    elif a.action=='publish':publish_due(items)
149:        upcoming=[e for e in items if datetime.fromisoformat(e['publish_at'])>datetime.now(TZ)]
152:        (DATA/'ENABLED').touch();print('Daily publishing enabled for calendar dates, 18:00–19:00 America/Santiago')
156:            s=read(item_state(e),{});print(e['publish_at'],e['family'],s.get('stage','pending'),json.dumps(s.get('platforms',{})))
/opt/mathrelaxing-auto/calendar.json:7:  "daily_publish_time": "18:00",
/opt/mathrelaxing-auto/calendar.json:13:    "on_failed_render": "skip_due_item_and_alert; do not publish unvalidated media",
/opt/mathrelaxing-auto/calendar.json:14:    "on_ambiguous_publish": "record needs_review; reconcile before retry",
/opt/mathrelaxing-auto/calendar.json:24:      "publish_at": "2026-10-21T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:116:        "youtube_description": "Three Stars from One Equation. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:118:        "instagram_caption": "Three Stars from One Equation. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:121:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:129:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:138:      "publish_at": "2026-10-22T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:219:        "youtube_description": "One Equation, Endless Transformations. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:221:        "instagram_caption": "One Equation, Endless Transformations. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:224:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:232:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:241:      "publish_at": "2026-10-23T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:324:        "youtube_description": "The Butterfly Hidden in Chaos. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:326:        "instagram_caption": "The Butterfly Hidden in Chaos. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:329:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:337:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:346:      "publish_at": "2026-10-24T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:428:        "youtube_description": "When 3 Meets 2. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:430:        "instagram_caption": "When 3 Meets 2. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:433:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:441:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:450:      "publish_at": "2026-10-25T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:541:        "youtube_description": "Two Sources, a Field of Interference. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:543:        "instagram_caption": "Two Sources, a Field of Interference. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:546:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:554:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:563:      "publish_at": "2026-10-26T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:655:        "youtube_description": "Circles Become a Star. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:657:        "instagram_caption": "Circles Become a Star. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:660:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:668:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:677:      "publish_at": "2026-10-27T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:758:        "youtube_description": "A Fractal in Motion. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:760:        "instagram_caption": "A Fractal in Motion. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:763:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:771:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:780:      "publish_at": "2026-10-28T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:861:        "youtube_description": "Order Inside a Chaotic Orbit. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:863:        "instagram_caption": "Order Inside a Chaotic Orbit. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:866:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:874:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:883:      "publish_at": "2026-10-29T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:965:        "youtube_description": "A 5-to-4 Rhythm You Can See. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:967:        "instagram_caption": "A 5-to-4 Rhythm You Can See. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:970:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:978:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:987:      "publish_at": "2026-10-30T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:1086:        "youtube_description": "Four Sources Drawing Interference. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:1088:        "instagram_caption": "Four Sources Drawing Interference. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:1091:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:1099:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:1108:      "publish_at": "2026-10-31T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:1200:        "youtube_description": "A Ten-Spoke Pattern in Simulated Sand. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:1202:        "instagram_caption": "A Ten-Spoke Pattern in Simulated Sand. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:1205:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:1213:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:1222:      "publish_at": "2026-11-01T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:1303:        "youtube_description": "Small Changes, Different Fractals. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:1305:        "instagram_caption": "Small Changes, Different Fractals. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:1308:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:1316:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:1325:      "publish_at": "2026-11-02T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:1408:        "youtube_description": "Chaos from Another Angle. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:1410:        "instagram_caption": "Chaos from Another Angle. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:1413:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:1421:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:1430:      "publish_at": "2026-11-03T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:1512:        "youtube_description": "Tracing a 7-to-5 Pattern. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:1514:        "instagram_caption": "Tracing a 7-to-5 Pattern. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:1517:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:1525:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:1534:      "publish_at": "2026-11-04T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:1621:        "youtube_description": "One Source, Expanding Rings. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:1623:        "instagram_caption": "One Source, Expanding Rings. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:1626:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:1634:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:1643:      "publish_at": "2026-11-05T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:1735:        "youtube_description": "The Geometry of a Circular Field. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:1737:        "instagram_caption": "The Geometry of a Circular Field. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:1740:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:1748:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:1757:      "publish_at": "2026-11-06T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:1838:        "youtube_description": "Inside a Moving Fractal Boundary. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:1840:        "instagram_caption": "Inside a Moving Fractal Boundary. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:1843:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:1851:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:1860:      "publish_at": "2026-11-07T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:1941:        "youtube_description": "A Symmetric System with a Complex Path. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:1943:        "instagram_caption": "A Symmetric System with a Complex Path. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:1946:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:1954:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:1963:      "publish_at": "2026-11-08T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:2045:        "youtube_description": "A 4-to-3 Curve in Motion. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:2047:        "instagram_caption": "A 4-to-3 Curve in Motion. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:2050:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:2058:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:2067:      "publish_at": "2026-11-09T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:2162:        "youtube_description": "Three Sources, Shifting Symmetry. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:2164:        "instagram_caption": "Three Sources, Shifting Symmetry. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:2167:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:2175:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:2184:      "publish_at": "2026-11-10T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:2276:        "youtube_description": "Rings, Spokes, and Simulated Sand. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:2278:        "instagram_caption": "Rings, Spokes, and Simulated Sand. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:2281:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:2289:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:2298:      "publish_at": "2026-11-11T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:2379:        "youtube_description": "The Same Rule, a Different Journey. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:2381:        "instagram_caption": "The Same Rule, a Different Journey. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:2384:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:2392:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:2401:      "publish_at": "2026-11-12T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:2484:        "youtube_description": "Two Wings of a Chaotic System. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:2486:        "instagram_caption": "Two Wings of a Chaotic System. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:2489:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:2497:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:2506:      "publish_at": "2026-11-13T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:2588:        "youtube_description": "A 5-to-3 Curve from Two Sines. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:2590:        "instagram_caption": "A 5-to-3 Curve from Two Sines. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:2593:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:2601:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:2610:      "publish_at": "2026-11-14T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:2702:        "youtube_description": "Changing the Phase Changes the Pattern. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:2704:        "instagram_caption": "Changing the Phase Changes the Pattern. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:2707:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:2715:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:2724:      "publish_at": "2026-11-15T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:2816:        "youtube_description": "Three Modes, One Circular Canvas. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:2818:        "instagram_caption": "Three Modes, One Circular Canvas. Which pattern is your favorite?\n\nArtistic particle model inspired by cymatics. Audio tones are not measured plate resonances. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:2821:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:2829:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:2838:      "publish_at": "2026-11-16T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:2919:        "youtube_description": "A Fractal Finale in Blue and Gold. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:2921:        "instagram_caption": "A Fractal Finale in Blue and Gold. Which transformation would you watch again?\n\nComputer-generated visualization of the quadratic Julia family. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:2924:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:2932:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:2941:      "publish_at": "2026-11-17T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:3022:        "youtube_description": "A Final Turn Through the Thomas Attractor. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:3024:        "instagram_caption": "A Final Turn Through the Thomas Attractor. Can you follow the trajectory?\n\nNumerical visualization of a mathematical dynamical system. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:3027:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:3035:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:3044:      "publish_at": "2026-11-18T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:3126:        "youtube_description": "A 7-to-4 Curve from Simple Motion. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:3128:        "instagram_caption": "A 7-to-4 Curve from Simple Motion. Which frequency ratio should we try next?\n\nParametric mathematical animation, not a measured physical experiment. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:3131:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:3139:        "instagram": {
/opt/mathrelaxing-auto/calendar.json:3148:      "publish_at": "2026-11-19T18:00:00-03:00",
/opt/mathrelaxing-auto/calendar.json:3231:        "youtube_description": "Six Sources in a Ring. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#Shorts #MathRelaxing #MathArt",
/opt/mathrelaxing-auto/calendar.json:3233:        "instagram_caption": "Six Sources in a Ring. Where do you see the strongest interference?\n\nIdealized mathematical interference field, not a full physical wave simulation. Original, procedurally generated melodic ambient music.\n\nFollow @MathRelaxing for more mathematical patterns.\n\n#MathRelaxing #MathArt #GenerativeArt #CreativeCoding"
/opt/mathrelaxing-auto/calendar.json:3236:        "youtube": {
/opt/mathrelaxing-auto/calendar.json:3244:        "instagram": {
root@ubuntu-4gb-hil-1:~#