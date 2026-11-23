"""Exercise saved templates and the real batch exporter with distinct media."""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.meta_path[:] = [f for f in sys.meta_path if type(f).__module__ != '_clipskitty_script_host']
from core.binaries import ffmpeg
from server.montage_api import snapshot
from server.montage_jobs import run
from video_editor.montage import Montage, TemplateStore, check_files
from video_editor.montage_render import probe

def encode(*args):
    result = subprocess.run([ffmpeg(), '-y', '-v', 'error', *map(str, args)], capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result.stdout

with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
    work = Path(directory)
    original = work / 'original.mp4'
    encode('-f', 'lavfi', '-i', 'color=white:s=180x320:r=30:d=1.7', '-c:v', 'libx264', original)
    sources = []
    for color in ('red', 'green', 'blue'):
        path = work / f'{color}.mp4'
        encode('-f', 'lavfi', '-i', f'color={color}:s=180x160:r=30:d=4', '-c:v', 'libx264', path)
        sources.append(str(path))
    template = Montage.model_validate({
        'name': 'Multiple sources', 'folder': str(work / 'export'), 'encoder': 'cpu',
        'width': 180, 'height': 320,
        'split': {'enabled': True, 'files': sources, 'bouncing_ball': True,
                  'speed': 2.3, 'random_start': False, 'loop': False}
    })
    store = TemplateStore(work)
    identifier = store.save('', template, False)
    payload = snapshot(work, identifier)
    assert payload['split']['files'] == sources and payload['split']['bouncing_ball']
    class Clips:
        def __init__(self):
            self.ids = []
        def get_clip(self, cid):
            self.ids.append(cid)
            return {'id': cid, 'video_id': 'synthetic', 'path': str(original), 'score': 90}
        def set_flag(self, key, value):
            self.result = json.loads(value)
    db = Clips()
    config = {'paths': {'data_dir': str(work)}}
    files = list(map(Path, run(db, config, 100, {'montage': payload, 'clip_ids': [5, 9]}, None)))
    assert db.ids == [5, 9] and len(files) == 8 and len(set(files)) == 8
    assert len(db.result['files']) == 8
    def rgb(path, time, region):
        return encode('-ss', time, '-i', path, '-vf', region, '-frames:v', 1, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-')
    lower_pixel = 'crop=2:2:88:256'
    scene_frames = []
    for index in range(2):
        for channel, path in enumerate(files[index*4:index*4+3]):
            color = rgb(path, 0.5, lower_pixel)[:3]
            assert color[channel] > 80 and all(value < 30 for i,value in enumerate(color) if i != channel), color
        ball = files[index*4+3]
        assert 'ball' in ball.name
        assert probe(ball)['fps'] == 60
        assert probe(files[index*4])['fps'] == 30
        at = rgb(ball, 0.5, 'crop=180:108:0:212')
        assert at and at != rgb(ball, 0.8, 'crop=180:108:0:212')
        assert at != rgb(ball, 0.517, 'crop=180:108:0:212'), 'Adjacent animation frames should contain new motion'
        scene_frames.append(hashlib.sha256(at).hexdigest())
    assert len(set(scene_frames)) == 2
    for path in files:
        assert abs(probe(path)['duration']-1.7) < 0.08
        assert min(rgb(path, 0.5, 'crop=2:2:88:40')[:3]) > 220
    for index, settings in enumerate([
        {'enabled': True, 'files': sources, 'bouncing_ball': False},
        {'enabled': True, 'bouncing_ball': True, 'file': 'unused-old-file.mp4', 'selection': 'fixed'},
        {'enabled': True, 'file': sources[0], 'selection': 'fixed'},
    ]):
        variant = {**payload, 'split': settings}
        check_files(Montage.model_validate(variant))
        outputs = run(db, config, 101+index, {'montage': variant, 'clip_ids': [5]}, None)
        assert len(outputs) == [3, 1, 1][index]
    print('PASS: three distinct secondary files plus generated rings per selected clip; duration, legacy templates, and ball-only mode preserved')
