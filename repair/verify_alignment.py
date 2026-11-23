import sys, subprocess, json, os, sqlite3
from pathlib import Path
sys.meta_path[:] = [f for f in sys.meta_path if type(f).__module__ != '_clipskitty_script_host']
from core.binaries import ffmpeg
from video_editor.montage import Montage,Split
from video_editor.montage_render import prepare,probe
import numpy as np

WORK=Path(__file__).resolve().parent/'alignment-check'; WORK.mkdir(exist_ok=True)
def run(args):
    return subprocess.run([ffmpeg(),'-y','-v','error',*map(str,args)],capture_output=True,check=True)
main=WORK/'pillarbox.mp4'; extra=WORK/'extra.mp4'
run(['-f','lavfi','-i','color=white:s=180x480:r=30','-vf','pad=320:480:70:0:black','-t','1','-c:v','libx264',main])
run(['-f','lavfi','-i','color=blue:s=280x160:r=30','-vf','pad=320:160:20:0:black','-t','1','-c:v','libx264',extra])
base={'name':'Aligned','width':320,'height':568,'encoder':'cpu','split':{'enabled':True,'file':str(extra),'selection':'fixed','random_start':False,'main_ratio':60,'speed':2.3}}
for top in (True,False):
    template=Montage.model_validate({**base,'split':{**base['split'],'main_top':top}})
    path=WORK/f'aligned-{top}.mov'
    manifest=prepare(main,path,template)
    assert manifest['main_visible_rect']==(70,0,180,480),manifest
    assert manifest['secondary_visible_rect']==(20,0,280,160),manifest
    assert manifest['content_width']==320 and manifest['fill_frame'] is True
    rgb=np.frombuffer(run(['-ss','0.4','-i',path,'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-']).stdout,dtype=np.uint8).reshape(568,320,3)
    first=np.where(rgb[80].max(axis=1)>80)[0]
    second=np.where(rgb[480].max(axis=1)>80)[0]
    assert abs(int(first[0])-int(second[0]))<=2 and abs(int(first[-1])-int(second[-1]))<=2,(first,second)
    assert first[0]==0 and first[-1]==319 and len(first)==320
    assert second[0]==0 and second[-1]==319 and len(second)==320
    assert abs(probe(path)['duration']-1)<0.1
    run(['-ss','0.4','-i',path,'-frames:v','1',WORK/f'aligned-{top}.png'])
    print('PASS: both videos fill full frame width without borders, main_top=',top,'content width=',manifest['content_width'])
legacy=Montage.model_validate({**base,'split':{**base['split'],'match_main_width':False,'fill_frame':False}})
manifest=prepare(main,WORK/'legacy.mov',legacy)
assert manifest['content_width']==320
assert Split().fill_frame is True
print('PASS: filling enabled for existing templates by default; opt-out remains available')

# Letterbox borders above/below a landscape original are removed as well.
letterbox=WORK/'letterbox.mp4'
run(['-f','lavfi','-i','color=white:s=320x160:r=30','-vf','pad=320:240:0:40:black','-t','1','-c:v','libx264',letterbox])
manifest=prepare(letterbox,WORK/'letterbox-filled.mov',Montage.model_validate(base))
assert manifest['main_visible_rect']==(0,40,320,160),manifest
rgb=np.frombuffer(run(['-ss','0.4','-i',WORK/'letterbox-filled.mov','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-']).stdout,dtype=np.uint8).reshape(568,320,3)
assert rgb[:340].min()>180
assert (rgb[340:,:,2]>180).all()
print('PASS: baked top/bottom borders removed; every pixel in both blocks filled')

data=Path(os.environ['LOCALAPPDATA'])/'Clips Studio/data'
db=sqlite3.connect((data/'montage.db').as_uri()+'?mode=ro',uri=True)
row=db.execute('SELECT body FROM templates LIMIT 1').fetchone(); db.close()
if row:
    saved=json.loads(row[0]); saved.update(width=360,height=640,encoder='cpu',ads=[],include_no_ads=True)
    saved['music']['enabled']=False
    clips=sorted((data/'clips').rglob('*.mp4'))
    if clips:
        sample=WORK/'actual-original.mp4'
        run(['-ss','1','-i',clips[0],'-t','2','-c:v','libx264','-c:a','aac',sample])
        saved['split']['match_main_width']=True
        preview=WORK/'actual-aligned.mov'
        manifest=prepare(sample,preview,Montage.model_validate(saved))
        run(['-ss','0.5','-i',preview,'-frames:v','1',WORK/'actual-aligned.png'])
        print('PASS: user original + saved secondary rendered; content width=',manifest['content_width'])
print('ALL ALIGNMENT CHECKS PASSED')
