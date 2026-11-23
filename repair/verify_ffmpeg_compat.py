import inspect
import sys
import os
import json
import subprocess
from pathlib import Path
# The script host isolates user pipelines by default. This maintenance check
# intentionally exercises the packaged engine, without changing host settings.
sys.meta_path[:] = [f for f in sys.meta_path if type(f).__module__ != '_clipskitty_script_host']
from core.models import ClipCandidate
from video.cutter import cut_clip
from video.encoding import sampled_frames
from core.binaries import ffmpeg
print('FFmpeg:', ffmpeg())
assert '-fps_mode' in cut_clip.__code__.co_consts
assert '-vsync' not in cut_clip.__code__.co_consts
assert '-fps_mode' in sampled_frames.__code__.co_consts
assert '-vsync' not in sampled_frames.__code__.co_consts
work = Path(__file__).resolve().parent
sources = sorted((Path(os.environ['LOCALAPPDATA']) / 'Clips Studio/data/downloads').glob('*.mp4'))
assert sources, 'No downloaded video for the render check'
source = sources[0]
print('Source:', source.name)
output = work / 'verified-clip.mp4'
cut_clip(source, ClipCandidate(start=10, end=12, score=100), output, final=True)
assert output.stat().st_size > 1000
probe = Path(ffmpeg()).with_name('ffprobe.exe')
result = subprocess.run([str(probe), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(output)], capture_output=True, text=True, check=True)
info = json.loads(result.stdout)
assert any(s['codec_type'] == 'video' for s in info['streams'])
assert any(s['codec_type'] == 'audio' for s in info['streams'])
assert 1.9 <= float(info['format']['duration']) <= 2.2
video = next(s for s in info['streams'] if s['codec_type'] == 'video')
frames = list(sampled_frames(output, every=8, width=video['width'], height=video['height'], hwaccel=False))
assert len(frames) >= 3, len(frames)
print('PASS: actual packaged cut_clip created a 2-second video with audio')
print('PASS: actual packaged sampled_frames returned', len(frames), 'frames')
print('Output:', output)
