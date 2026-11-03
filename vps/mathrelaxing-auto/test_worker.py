import importlib.util,json,tempfile,unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('worker',Path(__file__).with_name('worker.py'))
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
class Clock(datetime):
    moment=datetime.fromisoformat('2026-10-21T18:05:00-03:00')
    @classmethod
    def now(cls,tz):return cls.moment.astimezone(tz)
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.old=w.DATA;w.DATA=self.root
        self.path=Path
        def mapped(x):
            if str(x)=='/var/lib/mathrelaxing-publisher-cli':return self.root/'journals'
            return Path(x)
        self.patch=patch.object(w,'Path',side_effect=mapped);self.patch.start()
        self.clock=patch.object(w,'datetime',Clock);self.clock.start()
        Clock.moment=datetime.fromisoformat('2026-10-21T18:05:00-03:00')
        self.entry={'id':'day01','publish_at':'2026-10-21T18:00:00-03:00'}
        w.write(w.item_state(self.entry),{'stage':'ready','draft_id':'draft01','platforms':{}})
        self.calls=[]
    def tearDown(self):
        self.patch.stop();self.clock.stop();w.DATA=self.old;self.tmp.cleanup()
    def runfake(self,args,timeout=0):
        self.calls.append(args)
        p=args[-1].removeprefix('--')
        if args[1]=='publicar':
            # YouTube ends with --privacidad public.
            platform='youtube' if '--youtube' in args else p
            record={'stage':{'youtube':'uploaded','facebook':'submitted','instagram':'published'}[platform]}
            w.write(self.root/'journals'/f'draft01-{platform}.json',record)
            return 'submitted'
        return {'youtube':'Privacidad: public\nProcesamiento: succeeded','facebook':'"publish_status": "published"','instagram':'Etapa local: published\nPublicación: https://example.test/reel/1'}[p]
    def test_disabled_and_wrong_window_do_not_publish(self):
        with patch.object(w,'run',self.runfake):w.publish_due([self.entry])
        self.assertFalse(self.calls)
        (self.root/'ENABLED').touch();Clock.moment=datetime.fromisoformat('2026-10-21T17:59:00-03:00')
        with patch.object(w,'run',self.runfake):w.publish_due([self.entry])
        self.assertFalse(self.calls)
        Clock.moment=datetime.fromisoformat('2026-10-22T18:05:00-03:00')
        with patch.object(w,'run',self.runfake):w.publish_due([self.entry])
        self.assertFalse(self.calls)
    def test_all_confirmed_platforms_are_not_repeated(self):
        (self.root/'ENABLED').touch()
        with patch.object(w,'run',self.runfake):
            w.publish_due([self.entry]);first=len(self.calls);w.publish_due([self.entry])
        self.assertEqual(len(self.calls),first)
        s=w.read(w.item_state(self.entry),{})
        self.assertTrue(all(v=='published' for v in s['platforms'].values()))
    def test_ambiguous_attempt_is_held(self):
        (self.root/'ENABLED').touch()
        w.write(self.root/'journals'/'draft01-youtube.json',{'stage':'uploading'})
        with patch.object(w,'run',self.runfake):w.publish_due([self.entry])
        self.assertFalse(any('--youtube' in a for a in self.calls))
        self.assertEqual(w.read(w.item_state(self.entry),{})['platforms']['youtube'],'needs_review')
    def test_private_youtube_is_not_reuploaded(self):
        (self.root/'ENABLED').touch()
        w.write(self.root/'journals'/'draft01-youtube.json',{'stage':'uploaded'})
        def fake(args,timeout=0):
            if '--youtube' in args:
                self.calls.append(args);return 'Privacidad: private\nProcesamiento: succeeded'
            return self.runfake(args,timeout)
        with patch.object(w,'run',fake):w.publish_due([self.entry])
        self.assertEqual(w.read(w.item_state(self.entry),{})['platforms']['youtube'],'needs_review')
        self.assertFalse(any(a[1]=='publicar' and '--youtube' in a for a in self.calls))
if __name__=='__main__':unittest.main()
