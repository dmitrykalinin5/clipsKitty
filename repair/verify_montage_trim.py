import sys,os,json,subprocess,copy,yaml
from pathlib import Path
sys.meta_path[:]=[f for f in sys.meta_path if type(f).__module__!='_clipskitty_script_host']
import numpy as np
from core.binaries import ffmpeg
from core.models import ClipCandidate
from core.pipeline import _render_files
from video_editor.montage_render import probe
from video_editor.montage import Montage
import server.montage_jobs as jobs
from server.montage_jobs import _clean_main_for_mirror
WORK=Path(__file__).parent/'montage-trim-check';WORK.mkdir(exist_ok=True)
data=WORK/'data';(data/'downloads').mkdir(parents=True,exist_ok=True)
def run(args):
    r=subprocess.run([ffmpeg(),'-y','-v','error',*map(str,args)],capture_output=True)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
    return r.stdout
source=data/'downloads/test.mp4'
run(['-f','lavfi','-i','testsrc2=s=180x320:r=30','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t',8,'-c:v','libx264','-c:a','aac',source])
config=yaml.safe_load((Path(os.environ['LOCALAPPDATA'])/'Clips Studio/settings.yaml').read_text(encoding='utf8'))
config['paths']['data_dir']=str(data)
config['clips'].update(outro=False,normalize=False)
opts={'vertical_live':True,'captions':True,'caption_lines':[{'start':0,'end':2,'text':'WRONG BEGINNING'}, {'start':3,'end':5,'text':'SELECTED MIDDLE'}],
      'edit':{'keep':[[3,5]],'speed':1}}
original,_=_render_files(source,ClipCandidate(start=0,end=8,score=1),[],WORK/'original',copy.deepcopy(config),copy.deepcopy(opts))
row={'id':1,'video_id':'test','path':str(original),'start_s':0.,'end_s':8.,'score':1,'render_opts':json.dumps(opts)}
(WORK/'clean').mkdir(exist_ok=True)
clean,ass=_clean_main_for_mirror(data,row,config,WORK/'clean',None)
print('DURATIONS',probe(original)['duration'],probe(clean)['duration'])
def pixels(path,t):
    return np.frombuffer(run(['-ss',t,'-i',path,'-frames:v',1,'-vf','scale=90:160','-f','rawvideo','-pix_fmt','rgb24','-']),np.uint8).astype(float)
actual=pixels(clean,.2)
selected=pixels(source,3.2);begin=pixels(source,.2)
print('DIFF selected/start',np.mean(abs(actual-selected)),np.mean(abs(actual-begin)))
assert np.mean(abs(actual-selected))<np.mean(abs(actual-begin))*0.4,'Wrong source interval after clean render'
assert abs(probe(clean)['duration']-2)<.15
assert 'WRONG BEGINNING' not in ass.read_text(encoding='utf8')
assert 'SELECTED' in ass.read_text(encoding='utf8')
print('PASS selected interval preserved')
class DB:
    def get_clip(self,cid):return row
    def set_flag(self,key,value):pass
for index,(keep,speed) in enumerate([([[2.4,4.1]],1),([[2,5.4]],1),([[2,3],[5,7]],1.5)]):
    opts['edit']={'keep':keep,'speed':speed}
    opts['caption_lines']=[{'start':0,'end':1,'text':'WRONG BEGINNING'}, {'start':2.4,'end':2.8,'text':'MIDDLE'}, {'start':5,'end':6,'text':'TAIL'}]
    original,_=_render_files(source,ClipCandidate(start=0,end=8,score=1),[],WORK/f'case-{index}',copy.deepcopy(config),copy.deepcopy(opts))
    row.update(path=str(original),render_opts=json.dumps(opts))
    for mirrored in (False,True):
        template=Montage.model_validate({'name':'Trim regression','width':180,'height':320,'encoder':'cpu','mirror_main':mirrored,'main_framing':'crop'})
        files=jobs.run(DB(),config,900+index*2+int(mirrored),{'montage':template.model_dump(),'clip_ids':[1],'folder':str(WORK/'exports')},None)
        output=Path(files[0]);expected=sum(b-a for a,b in keep)/speed
        assert abs(probe(output)['duration']-expected)<.15,(keep,speed,probe(output)['duration'])
        # Compare the actual exported moving picture to the selected source,
        # excluding the subtitle area and undoing the requested reflection.
        def frame(path,t,flip=False):
            filters=('hflip,' if flip else '')+'scale=180:320,crop=180:180:0:0'
            return np.frombuffer(run(['-ss',t,'-i',path,'-frames:v',1,'-vf',filters,'-f','rawvideo','-pix_fmt','rgb24','-']),np.uint8).astype(float)
        offset=.2
        selected=frame(source,keep[0][0]+offset*speed)
        actual=frame(output,offset,mirrored)
        wrong=frame(source,offset)
        reference=frame(original,offset)
        assert np.mean(abs(actual-reference))<5,(keep,mirrored,'template changed edited frames')
        selection_error=min(np.mean(abs(actual-frame(source,keep[0][0]+offset*speed+delta))) for delta in (-.07,-.035,0,.035,.07))
        assert selection_error<np.mean(abs(actual-wrong))*.7,(keep,mirrored,selection_error,np.mean(abs(actual-wrong)))
        def pcm(path,t):
            return np.frombuffer(run(['-ss',t,'-i',path,'-t',.3,'-vn','-ac',1,'-ar',8000,'-f','f32le','-']),np.float32)
        # Template must retain the already edited audio, including cuts/speed.
        a,b=pcm(output,.2),pcm(original,.2)
        corr=np.correlate(a,b,'full').max()/(np.linalg.norm(a)*np.linalg.norm(b))
        assert corr>.9,corr
        print('PASS export: keep=',keep,'speed=',speed,'mirror=',mirrored,'duration=',expected,'audio=',round(float(corr),3))
print('ALL TEMPLATE TRIM CHECKS PASSED')
