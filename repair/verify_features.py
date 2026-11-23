"""Isolated integration checks. All outputs and databases stay in repair/."""
import sys, json, hashlib, shutil, subprocess
from pathlib import Path
sys.meta_path[:] = [f for f in sys.meta_path if type(f).__module__ != '_clipskitty_script_host']
import video.outro as outro
from core.binaries import ffmpeg, ffprobe
from video_editor.montage import Montage, TemplateStore
from server.montage_api import snapshot
import server.montage_jobs as jobs

ROOT=Path(__file__).resolve().parent
WORK=ROOT/'feature-check'; WORK.mkdir(exist_ok=True)
source=ROOT/'verified-clip.mp4'
assert source.is_file()
digest=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
original=digest(source)
for config in ({}, {'clips':{'outro':True}}, {'clips':{'outro':False}}):
    assert not outro.enabled(config)
    assert not outro.append(source,config)
assert digest(source)==original
assert not hasattr(outro,'ensure_outro') and not hasattr(outro,'frames')
assert not outro.summary()
copy=WORK/'before-finish.mp4'; shutil.copyfile(source,copy)
finished=WORK/'finished.mp4'
outro.finish(copy,finished,{'clips':{'outro':True}})
assert digest(finished)==original and not copy.exists()
print('PASS: end-card generator removed; enabled=true cannot add branding; finish preserves bytes')

def media_info(path):
    result=subprocess.run([ffprobe(),'-v','error','-show_streams','-show_format','-of','json',str(path)],capture_output=True,text=True,check=True)
    return json.loads(result.stdout)

# Actual video, music and advertisement assets, small enough for repeatable tests.
second=WORK/'second.mp4'; music=WORK/'music.wav'; ad=WORK/'advertisement.mp4'
def generate(args):
    subprocess.run([ffmpeg(),'-y','-v','error',*args],check=True)
generate(['-f','lavfi','-i','color=c=blue:s=160x160:r=30','-t','3','-c:v','libx264',str(second)])
generate(['-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','3',str(music)])
generate(['-f','lavfi','-i','color=c=red:s=160x160:r=30','-f','lavfi','-i','sine=frequency=880:sample_rate=48000','-t','0.5','-c:v','libx264','-c:a','aac',str(ad)])
settings=Montage.model_validate({'name':'Integration test','width':180,'height':320,'encoder':'cpu','folder':str(WORK/'exports'),
    'split':{'enabled':True,'file':str(second),'selection':'fixed','random_start':False},
    'music':{'enabled':True,'file':str(music),'selection':'fixed','duck':False},
    'ads':[{'name':'Test ad','file':str(ad),'duration':0.5,'timing':'manual','seconds':0.7,'effect':'cut','entrance':'none','exit':'none'}],
    'include_no_ads':True}).model_dump()
store=TemplateStore(WORK)
identifier=store.save('',Montage.model_validate(settings),False)
assert snapshot(WORK,identifier)['split']['file']==str(second)
chosen=snapshot(WORK,{**settings,'clip_limit':1})
assert chosen['clip_limit']==1 and chosen['ads'][0]['file']==str(ad)
assert snapshot(WORK,False) is False
for bad in (0,-1,1.5,'2',True):
    try: snapshot(WORK,{**settings,'clip_limit':bad})
    except Exception as e: assert getattr(e,'status_code',None)==400
    else: raise AssertionError(bad)
print('PASS: saved template resolves; count survives snapshot; invalid counts rejected')
from server.api import BatchItemIn, LocalVideoIn, _process_options
for mode in ('podcast','gaming'):
    body=BatchItemIn.model_validate({'url':'https://www.youtube.com/watch?v=test1234567','montage':{**settings,'clip_limit':2},'montage_template_id':identifier,mode:True})
    options=_process_options(body,data_dir=WORK)
    assert options['montage']['clip_limit']==2
    assert options[mode] is True
body=LocalVideoIn.model_validate({'path':str(source),'montage':{**settings,'clip_limit':1},'montage_template_id':identifier})
assert _process_options(body,data_dir=WORK)['montage']['clip_limit']==1
print('PASS: batch URL and local-file request models preserve template/count alongside podcast/gaming')

class DB:
    def __init__(self):
        self.rows=[{'id':1,'score':50,'video_id':'test','path':str(source)}, {'id':2,'score':90,'video_id':'test','path':str(source)}, {'id':3,'score':70,'video_id':'test','path':str(source)}]
        self.flags={}
    def clips_for_video(self,video_id):
        assert video_id=='test'
        return self.rows
    def get_clip(self,identifier):
        return next(row for row in self.rows if row['id']==identifier)
    def set_flag(self,key,value): self.flags[key]=value

db=DB(); cfg={'paths':{'data_dir':str(WORK)}}
files=jobs.run(db,cfg,999,{'montage':chosen,'video_id':'test'},None)
assert len(files)==2,files
assert all('clip_2__' in str(f) for f in files),files
for file in files:
    info=media_info(file)
    assert any(s['codec_type']=='video' and s['width']==180 and s['height']==320 for s in info['streams'])
    assert any(s['codec_type']=='audio' for s in info['streams'])
    assert 1.9 <= float(info['format']['duration']) <= 2.8
assert 'montage_result:999' in db.flags
print('PASS: limited job exported only highest-rated clip, with second video/music and both ad/no-ad variants')

# Exercise selection for all clips, two clips, oversized limit and explicit IDs
# without repeating the expensive renders.
calls=[]
real_export=jobs.export_variants
def record(*args,**kwargs):
    calls.append(args[2])
    return []
jobs.export_variants=record
for limit,expected,ids in [(None,['clip_1','clip_2','clip_3'],None),(2,['clip_2','clip_3'],None),(9,['clip_2','clip_3','clip_1'],None),(1,['clip_3'],[3,1])]:
    calls.clear()
    payload={'montage':{**settings,**({'clip_limit':limit} if limit else {})},'video_id':'test'}
    if ids: payload['clip_ids']=ids
    jobs.run(db,cfg,1000,payload,None)
    assert calls==expected,(limit,calls)
jobs.export_variants=real_export
print('PASS: all-clips mode, N=2, N greater than available, explicit selection')
print('ALL FEATURE CHECKS PASSED')
