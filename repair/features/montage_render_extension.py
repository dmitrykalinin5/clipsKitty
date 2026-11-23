"""Composition with independent speed for the secondary video/audio stream."""
from functools import lru_cache
from contextvars import ContextVar
from math import ceil
_main_subtitles = ContextVar('montage_main_subtitles', default=None)

_export_before_mirror = export_variants
def export_variants(source, folder, name, template, *, index=0, segments=(), token=None,
                    on_progress=None, caption_path=None):
    handle = _main_subtitles.set(str(caption_path) if caption_path else None)
    try:
        split = template.split
        if not split.enabled or not (split.files or split.bouncing_ball):
            return _export_before_mirror(source, folder, name, template, index=index,
                segments=segments, token=token, on_progress=on_progress)

        check_files(template)
        choices = []
        for number, path in enumerate(dict.fromkeys(split.files), 1):
            options = {'file': path, 'selection': 'fixed', 'files': [], 'bouncing_ball': False}
            choices.append((f'{name}_video_{number:02d}', split.model_copy(update=options)))
        if split.bouncing_ball:
            options = {'files': [], 'match_main_width': False, 'random_start': False, 'loop': False}
            choices.append((f'{name}_ball', split.model_copy(update=options)))

        variants_per_source = int(template.include_no_ads) + len(template.ads)
        total = len(choices) * variants_per_source
        files = []
        for position, (variant_name, variant_split) in enumerate(choices):
            _check(token)
            offset = position * variants_per_source

            def report(current, _total):
                if on_progress:
                    on_progress(offset + current, total)

            report(0, total)
            settings = template.model_copy(update={'split': variant_split})
            files.extend(_export_before_mirror(source, folder, variant_name, settings, index=index,
                segments=segments, token=token, on_progress=report))
        return files
    finally:
        _main_subtitles.reset(handle)

def _subtitle_filter(path):
    # FFmpeg filter parser has two escaping layers inside filter_complex.
    value = str(Path(path).resolve()).replace('\\','/')
    value = value.replace(':', '\\:').replace("'", "'\\''")
    return "subtitles=filename='"+value+"'"

@lru_cache(maxsize=256)
def _visible_rect_cached(path, size, modified, width, height, duration):
    """Union of several samples; remove only substantial symmetric borders."""
    bounds = []
    for fraction in (0.15, 0.5, 0.85):
        _check(None)
        result = subprocess.run([ffmpeg(), '-hide_banner', '-v', 'info',
            '-ss', str(max(0, min(duration*fraction, duration-0.15))), '-i', path,
            '-an', '-sn', '-t', '0.35', '-vf', 'cropdetect=limit=20:round=2:reset=0',
            '-f', 'null', '-'], capture_output=True, timeout=20)
        found = re.findall(rb'crop=(\d+):(\d+):(\d+):(\d+)', result.stderr)
        if result.returncode or not found:
            return 0, 0, width, height
        left = min(int(item[2]) for item in found)
        right = max(int(item[2])+int(item[0]) for item in found)
        top = min(int(item[3]) for item in found)
        bottom = max(int(item[3])+int(item[1]) for item in found)
        bounds.append((left, right, top, bottom))
    left = min(b[0] for b in bounds)//2*2
    right = min(width, (max(b[1] for b in bounds)+1)//2*2)
    bar_left, bar_right = left, width-right
    if (min(bar_left,bar_right) < max(4,width*0.015) or
        abs(bar_left-bar_right) > max(8,width*0.05) or right-left < width*0.35):
        left,right = 0,width
    top = min(b[2] for b in bounds)//2*2
    bottom = min(height,(max(b[3] for b in bounds)+1)//2*2)
    if (min(top,height-bottom) < max(4,height*0.015) or
        abs(top-(height-bottom)) > max(8,height*0.05) or bottom-top < height*0.35):
        top,bottom = 0,height
    return left,top,right-left,bottom-top

def _visible_rect(path, info, token=None):
    _check(token)
    v = info['video']
    width, height = int(v['width']), int(v['height'])
    stat = Path(path).stat()
    try:
        result = _visible_rect_cached(str(Path(path).resolve()),stat.st_size,stat.st_mtime_ns,width,height,info['duration'])
    except (OSError,subprocess.TimeoutExpired):
        result = (0,0,width,height)
    _check(token)
    return result

def prepare(source, output, template, index=0, token=None, rng=None):
    rng = rng or random.SystemRandom()
    info = probe(source)
    if not info['video'] or info['duration'] <= 0:
        raise ValueError(f'No playable video: {source}')
    fps, frames = info['fps'], info['frames']
    duration = frames / float(fps)
    if template.split.enabled and template.split.bouncing_ball and fps < 59:
        # Keep the clip's exact frame duration even at fractional source rates.
        factor = ceil(59 / fps)
        fps *= factor
        frames *= factor
    width, height = template.width, template.height
    inputs, graph = ['-i', str(source)], []
    manifest = {'source': str(source), 'fps': str(fps), 'frames': frames}
    audio = '0:a' if info['audio'] else None

    def fit(label, w, h, out, crop=False, speed=1.0, frame_crop=None, mirror=False,
            blurred=False, subtitle_path=None, scale=1.0):
        scaling = (f'scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2,crop={w}:{h}' if crop else
                   f'scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2')
        timing = f'setpts=(PTS-STARTPTS)/{speed:.12g},' if speed != 1 else ''
        trimming = f'crop={frame_crop[2]}:{frame_crop[3]}:{frame_crop[0]}:{frame_crop[1]},' if frame_crop else ''
        prefix = trimming+timing+('hflip,' if mirror else '')
        clock = f'setsar=1,fps={fps},settb=AVTB,setpts=N/({fps}*TB)'
        subtitle = _subtitle_filter(subtitle_path)+',' if subtitle_path else ''
        if blurred:
            fw,fh = max(2,int(w*scale)//2*2),max(2,int(h*scale)//2*2)
            graph.append(f'[{label}]{prefix}split=2[{out}_bg_in][{out}_fg_in]')
            graph.append(f'[{out}_bg_in]scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2,crop={w}:{h},gblur=sigma=25,{clock}[{out}_bg]')
            graph.append(f'[{out}_fg_in]{subtitle}scale={fw}:{fh}:force_original_aspect_ratio=decrease:force_divisible_by=2,{clock}[{out}_fg]')
            graph.append(f'[{out}_bg][{out}_fg]overlay=(W-w)/2:(H-h)/2:shortest=1[{out}]')
        else:
            graph.append(f'[{label}]{prefix}{subtitle}{scaling},{clock}[{out}]')

    next_input = 1
    if template.split.enabled:
        opt = template.split
        speed = float(opt.speed)
        if not 0.5 <= speed <= 4.0:
            raise ValueError('Secondary video speed must be between 0.5 and 4')
        main_h = int(height * opt.main_ratio / 100) // 2 * 2
        needed = duration * speed
        if opt.bouncing_ball:
            selected = str(output.with_name('bouncing-ball.mp4'))
            manifest['ball_scene'] = _render_bouncing_ball(
                selected, width, height-main_h, fps, duration, speed, rng, token)
            needed = duration
        else:
            selected = _pick(opt, 'video', index, rng)
        secondary = probe(Path(selected))
        if not secondary['video'] or secondary['duration'] <= 0:
            raise ValueError(f'No playable secondary video: {selected}')
        if secondary['duration'] + 1e-6 < needed and not opt.loop:
            raise ValueError('Secondary video is shorter than the clip at the selected speed; enable looping')
        available = max(0, secondary['duration'] - needed)
        offset = rng.uniform(0, available) if opt.random_start else 0
        inputs += (['-stream_loop', '-1'] if opt.loop else []) + ['-ss', f'{offset:.9f}', '-i', selected]
        content_w = width
        main_crop = secondary_crop = None
        if opt.fill_frame or opt.match_main_width or template.main_framing=='blur':
            main_crop = _visible_rect(source,info,token)
            if not opt.bouncing_ball:
                secondary_crop = _visible_rect(selected,secondary,token)
        if not opt.bouncing_ball and not opt.fill_frame and opt.match_main_width and template.main_framing!='blur':
            sar = info['video'].get('sample_aspect_ratio','1:1')
            try:
                sar = float(Fraction(sar.replace(':','/')))
                if not 0 < sar < 10: sar = 1.0
            except (ValueError,ZeroDivisionError):
                sar = 1.0
            # Legacy matching mode keeps the original full-height framing.
            main_crop = (main_crop[0],0,main_crop[2],int(info['video']['height']))
            secondary_crop = (secondary_crop[0],0,secondary_crop[2],int(secondary['video']['height']))
            visible_ratio = main_crop[2]*sar / int(info['video']['height'])
            content_w = max(16,min(width,int(main_h*visible_ratio)//2*2))
        fit('0:v', content_w, main_h, 'main',crop=opt.fill_frame,frame_crop=main_crop,
            mirror=template.mirror_main,blurred=template.main_framing=='blur',
            subtitle_path=_main_subtitles.get(),scale=template.main_scale)
        fit('1:v', content_w, height-main_h, 'secondary', crop=True,
            speed=1.0 if opt.bouncing_ball else speed, frame_crop=secondary_crop, mirror=opt.mirror)
        order = '[main][secondary]' if opt.main_top else '[secondary][main]'
        stack = f'{order}vstack=inputs=2:shortest=1'
        if content_w < width:
            stack += f',pad={width}:{height}:(ow-iw)/2:0'
        graph.append(stack+'[vout]')
        next_input += 1
        manifest.update(secondary='bouncing-ball' if opt.bouncing_ball else selected,
                        secondary_offset=offset, secondary_speed=speed,
                        content_width=content_w, fill_frame=opt.fill_frame,
                        main_visible_rect=main_crop, secondary_visible_rect=secondary_crop)
        if not opt.mute and secondary['audio']:
            remaining, tempo = speed, []
            while remaining > 2:
                tempo.append('atempo=2')
                remaining /= 2
            tempo.append(f'atempo={remaining:.12g}')
            graph.append(f'[1:a]{",".join(tempo)},volume={opt.volume},atrim=duration={duration},asetpts=PTS-STARTPTS[extra]')
            if audio:
                graph.append(f'[{audio}][extra]amix=inputs=2:duration=first:normalize=0[with_extra]')
                audio = 'with_extra'
            else:
                audio = 'extra'
    else:
        fit('0:v', width, height, 'vout',crop=True,mirror=template.mirror_main,
            blurred=template.main_framing=='blur',subtitle_path=_main_subtitles.get(),scale=template.main_scale)

    if audio is None:
        graph.append(f'anullsrc=r=48000:cl=stereo,atrim=duration={duration}[voice]')
    else:
        graph.append(f'[{audio}]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={duration},asetpts=PTS-STARTPTS[voice]')
    if template.music.enabled:
        opt = template.music
        selected = _pick(opt, 'music', index, rng)
        if not probe(Path(selected))['audio']:
            raise ValueError(f'No audio stream in music file: {selected}')
        inputs += ['-stream_loop', '-1', '-i', selected]
        fade_in, fade_out = min(opt.fade_in, duration), min(opt.fade_out, duration)
        graph.append(f'[{next_input}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=duration={duration},asetpts=PTS-STARTPTS,volume={opt.volume},afade=t=in:d={fade_in},afade=t=out:st={duration-fade_out}:d={fade_out}[music]')
        if opt.duck:
            graph += ['[voice]asplit=2[speech][sidechain]', '[music][sidechain]sidechaincompress=threshold=0.02:ratio=12:attack=15:release=400[ducked]', '[speech][ducked]amix=inputs=2:duration=first:normalize=0[aout]']
        else:
            graph.append('[voice][music]amix=inputs=2:duration=first:normalize=0[aout]')
        manifest['music'] = selected
    else:
        graph.append('[voice]anull[aout]')
    _encode(inputs, ';'.join(graph), output, template, token, duration)
    return manifest
