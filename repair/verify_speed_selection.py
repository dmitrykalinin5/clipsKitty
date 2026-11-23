"""Real-media checks for arbitrary secondary speed and selected originals."""
import sys, subprocess, json, hashlib
from pathlib import Path
sys.meta_path[:] = [f for f in sys.meta_path if type(f).__module__ != '_clipskitty_script_host']
from core.binaries import ffmpeg, ffprobe
from video_editor.montage import Montage, Split, TemplateStore
from video_editor.montage_render import prepare
from server.montage_api import snapshot
import server.montage_jobs as jobs

WORK=Path(__file__).resolve().parent/'speed-check'
WORK.mkdir(exist_ok=True)
def run(args):
    return subprocess.run([ffmpeg(),'-y','-v','error',*map(str,args)],check=True,capture_output=True)
main=WORK/'original.mp4'; second=WORK/'colors.mp4'
run(['-f','lavfi','-i','color=c=white:s=180x320:r=30','-t','2','-c:v','libx264',main])
run(['-f','lavfi','-i','color=c=red:s=160x160:r=30:d=1',
     '-f','lavfi','-i','color=c=green:s=160x160:r=30:d=1',
     '-f','lavfi','-i','color=c=blue:s=160x160:r=30:d=1',
     '-f','lavfi','-i','color=c=yellow:s=160x160:r=30:d=1',
     '-f','lavfi','-i','sine=frequency=880:sample_rate=48000',
     '-filter_complex','[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0[v]',
     '-map','[v]','-map','4:a','-t','4','-c:v','libx264','-c:a','aac',second])
digest=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
before=digest(main)
base={'name':'Speed test','width':180,'height':320,'encoder':'cpu','folder':str(WORK/'exports'),
      'split':{'enabled':True,'file':str(second),'selection':'fixed','random_start':False,'mute':False,'loop':True}}
for speed,expected in [(0.5,'red'),(1,'red'),(2.3,'green'),(4,'blue')]:
    settings={**base,'split':{**base['split'],'speed':speed}}
    template=Montage.model_validate(settings)
    assert template.split.speed==speed
    store=TemplateStore(WORK)
    identifier=store.save('',template,False)
    assert snapshot(WORK,identifier)['split']['speed']==speed
    output=WORK/f'speed-{speed}.mov'
    manifest=prepare(main,output,template)
    assert manifest['secondary_speed']==speed
    result=subprocess.run([ffprobe(),'-v','error','-show_streams','-show_format','-of','json',str(output)],capture_output=True,text=True,check=True)
    info=json.loads(result.stdout)
    assert abs(float(info['format']['duration'])-2)<0.1
    assert any(s['codec_type']=='audio' for s in info['streams'])
    pixels=run(['-ss','0.6','-i',output,'-vf','crop=2:2:88:240','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-']).stdout
    r,g,b=pixels[:3]
    if expected=='red': assert r>150 and g<50 and b<50,(speed,r,g,b)
    if expected=='green': assert g>70 and r<50 and b<50,(speed,r,g,b)
    if expected=='blue': assert b>150 and r<50 and g<50,(speed,r,g,b)
    print('PASS speed',speed,'actual secondary frame:',expected,'duration/audio preserved; template saved/reloaded')
assert Split().speed==1
for speed in (0.49,4.01,float('nan'),float('inf')):
    try: Split(speed=speed)
    except ValueError: pass
    else: raise AssertionError(speed)
slow=Montage.model_validate({**base,'split':{**base['split'],'loop':False,'speed':0.5}})
prepare(main,WORK/'slow-no-loop.mov',slow)
fast=Montage.model_validate({**base,'split':{**base['split'],'loop':False,'speed':4}})
try: prepare(main,WORK/'too-short.mov',fast)
except ValueError as e: assert 'loop' in str(e)
else: raise AssertionError('Too-short secondary must fail without looping')
assert digest(main)==before
print('PASS: bounds, finite values, legacy default, speed-aware non-loop duration, original unchanged')

class DB:
    def __init__(self): self.flags={}; self.read=[]
    def get_clip(self,cid):
        self.read.append(cid)
        return {'id':cid,'video_id':'original','path':str(main),'score':cid}
    def set_flag(self,k,v): self.flags[k]=v
db=DB(); chosen=Montage.model_validate({**base,'split':{**base['split'],'speed':2.3}}).model_dump()
files=jobs.run(db,{'paths':{'data_dir':str(WORK)}},700,{'montage':chosen,'clip_ids':[3,7],'folder':str(WORK/'selected-exports')},None)
assert db.read==[3,7] and len(files)==2,(db.read,files)
assert all(Path(f).exists() for f in files)
assert digest(main)==before
print('PASS: only selected originals 3 and 7 exported with saved 2.3x template; originals untouched')
print('ALL SPEED AND SELECTION CHECKS PASSED')
