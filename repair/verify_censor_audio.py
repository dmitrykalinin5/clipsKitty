import sys,subprocess,json
from pathlib import Path
sys.meta_path[:]=[f for f in sys.meta_path if type(f).__module__!='_clipskitty_script_host']
import numpy as np
from core.binaries import ffmpeg,ffprobe
from video_editor.audio import mute_filter
from video_editor.timeline import EditList
from video_editor.export import apply_edits
WORK=Path(__file__).parent/'censor-check';WORK.mkdir(exist_ok=True)
def run(args):
    p=subprocess.run([ffmpeg(),'-y','-v','error',*map(str,args)],capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    return p.stdout
source=WORK/'original.mp4';output=WORK/'center-censored.mp4'
run(['-f','lavfi','-i','color=blue:s=160x240:r=30','-f','lavfi','-i','aevalsrc=0.2*sin(2*PI*440*t)|0.2*sin(2*PI*880*t):s=48000:d=3','-t','3','-c:v','libx264','-c:a','aac',source])
edit=EditList.from_dict({'keep':[[0,3]],'mutes':[[1.25,1.75]],'muted_words':[{'start':1,'end':2,'word':'блять'}]},duration=3)
apply_edits(source,edit,output,normalize=False,final=True)
def decode(path):
    return np.frombuffer(run(['-i',path,'-vn','-f','f32le','-acodec','pcm_f32le','-ac','2','-ar','48000','-']),dtype=np.float32).reshape(-1,2)
before,after=decode(source),decode(output)
def rms(arr,a,b):return np.sqrt(np.mean(arr[int(a*48000):int(b*48000)]**2,axis=0))
for a,b in [(0.2,0.8),(1.02,1.20),(1.80,1.98),(2.1,2.8)]:
    ratio=rms(after,a,b)/rms(before,a,b)
    assert (ratio>0.90).all() and (ratio<1.10).all(),(a,b,ratio)
assert (rms(after,1.3,1.7)<0.001).all(),rms(after,1.3,1.7)
info=json.loads(subprocess.run([ffprobe(),'-v','error','-show_streams','-show_format','-of','json',str(output)],capture_output=True,text=True,check=True).stdout)
assert next(s for s in info['streams'] if s['codec_type']=='audio')['channels']==2
assert abs(float(info['format']['duration'])-3)<0.1
# Direct lossless filtering verifies gentle transitions are confined to mute.
pcm=run(['-f','lavfi','-i','aevalsrc=0.2|0.4:s=48000:d=3','-af',mute_filter([(1.25,1.75)]),'-f','f32le','-acodec','pcm_f32le','-'])
samples=np.frombuffer(pcm,dtype=np.float32).reshape(-1,2)
assert np.allclose(samples[59000],[0.2,0.4],atol=1e-6)
assert np.allclose(samples[60000],[0.2,0.4],atol=1e-6)
assert (samples[60120]>0).all() and (samples[60120]<[0.2,0.4]).all()
assert np.allclose(samples[62000],[0,0],atol=1e-6)
assert np.allclose(samples[85000],[0.2,0.4],atol=1e-6)
assert np.max(np.abs(np.diff(samples,axis=0)))<0.003
assert mute_filter([])==''
print('PASS: real edit silences only word center; beginning/end/neighbors preserved; stereo and duration preserved')
print('PASS: sample-level 5ms ramps inside interval avoid hard clicks without extending the mute')
print('ALL CENSOR AUDIO CHECKS PASSED')
