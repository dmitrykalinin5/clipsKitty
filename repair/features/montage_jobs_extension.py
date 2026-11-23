"""Limit template application, while preserving the existing export engine."""
_run_without_limit = run

def _clean_main_for_mirror(data_dir, row, config, work, token):
    import copy
    from core.models import ClipCandidate, Segment
    from core.pipeline import _render_files,captions_on
    cancel.check(token)
    original = Path(row['path'])
    opts = json.loads(row.get('render_opts') or '{}')
    ass = original.with_suffix('.ass')
    from video_editor.timeline import EditList
    from video_editor.captions import remap_lines
    edit = EditList.from_dict(opts.get('edit') or {}, duration=row['end_s']-row['start_s'])
    # Sidecar ASS files may predate the edit and still use the source clock.
    # Rebuild captions after cuts/speed changes rather than reusing that clock.
    retimed = edit is not None and (edit.keep is not None or abs(edit.speed-1) > 1e-9)
    reuse_ass = ass.is_file() and not retimed
    if opts.get('captions') is False or opts.get('job_captions') is False:
        return original, None
    wants_captions = ass.is_file() or captions_on(config,opts)
    relative_segments = clip_segments(data_dir,row) if wants_captions and not reuse_ass else []
    if wants_captions and not reuse_ass and not relative_segments and not opts.get('caption_lines'):
        raise ValueError('Не удалось восстановить субтитры для безопасного отражения: отсутствуют и файл .ass, и расшифровка. Восстановите исходные данные клипа.')
    sources = [p for p in (data_dir/'downloads').glob(str(row['video_id'])+'.*') if p.suffix.lower() in ('.mp4','.mkv','.mov','.webm','.avi')]
    if not sources:
        raise ValueError('Для отзеркаливания без переворота субтитров нужен исходный видеоролик. Верните его в библиотеку и повторите экспорт.')
    transcript = data_dir/'transcripts'/f"{row['video_id']}.json"
    segments = []
    if transcript.is_file():
        segments = [Segment(**{k:v for k,v in s.items() if k in ('start','end','text','words')})
                    for s in json.loads(transcript.read_text(encoding='utf8')).get('segments',[])]
    cfg = copy.deepcopy(config)
    cfg.setdefault('clips',{})['outro'] = False
    opts.update(captions=False, job_captions=False)
    candidate = ClipCandidate(start=row['start_s'],end=row['end_s'],score=row['score'] or 0,hook=row.get('hook') or '')
    clean, _ = _render_files(sources[0],candidate,segments,work,cfg,opts,config.get('content_language','en'))
    cancel.check(token)
    if not wants_captions:
        return clean,None
    subtitle_copy = work/'captions.ass'
    if reuse_ass:
        # Reuse exact styling/timing when the intermediate ASS was kept.
        subtitle_copy.write_bytes(ass.read_bytes())
    else:
        from video.captions import build_captions
        from video_editor.montage_render import probe
        original_info=probe(original)
        duration=original_info['duration']
        style=json.loads(row.get('render_opts') or '{}').get('caption_style') or config.get('clips',{}).get('caption_style')
        lines=json.loads(row.get('render_opts') or '{}').get('caption_lines')
        if lines is not None and edit is not None:
            lines = remap_lines(lines, edit)
        relative=[Segment(**{k:v for k,v in s.items() if k in ('start','end','text','words')}) for s in relative_segments]
        subtitle_copy=build_captions(relative,ClipCandidate(start=0,end=duration,score=0),subtitle_copy,
            style=style,lines=lines,canvas=(int(original_info['video']['width']),int(original_info['video']['height'])),
            language=config.get('content_language','en'))
        if subtitle_copy is None:
            raise ValueError('Не удалось восстановить читаемые субтитры для отражения')
    return clean, subtitle_copy

def _run_mirrored(db,config,job_id,payload,token):
    import tempfile
    template=Montage.model_validate(payload['montage'])
    data_dir=Path(config['paths']['data_dir'])
    folder=Path(payload.get('folder') or template.folder or data_dir/'exports')/f'batch_{job_id}'
    folder.mkdir(parents=True,exist_ok=True)
    ids=payload.get('clip_ids')
    if ids is None: ids=[r['id'] for r in db.clips_for_video(payload['video_id'])]
    files=[]
    for index,cid in enumerate(ids):
        cancel.check(token)
        row=db.get_clip(cid)
        if row is None: raise ValueError(f'Clip {cid} not found')
        row=dict(row)
        segments=clip_segments(data_dir,row)
        def notify(n,total):
            progress.emit(stage='montage',current=index+1,total=len(ids),fraction=(index+n/max(1,total))/max(1,len(ids)),label=f'Montage clip {index+1}/{len(ids)}')
        with tempfile.TemporaryDirectory(prefix='.mirror-',dir=folder) as temporary:
            clean,ass=_clean_main_for_mirror(data_dir,row,config,Path(temporary),token)
            files.extend(export_variants(clean,folder,f'clip_{cid}',template,index=index,
                segments=segments,token=token,on_progress=notify,caption_path=ass))
        db.set_flag(f'montage_result:{job_id}',json.dumps({'files':files,'folder':str(folder)}))
    return files

def run(db, config, job_id, payload, token):
    settings = payload.get('montage')
    limit = settings.get('clip_limit') if isinstance(settings, dict) else None
    if limit is not None:
        if type(limit) is not int or limit < 1:
            raise ValueError('Количество клипов должно быть целым числом больше нуля')
        payload = dict(payload)
        payload['montage'] = {key: value for key, value in settings.items() if key != 'clip_limit'}
        ids = payload.get('clip_ids')
        if ids is None:
            rows = db.clips_for_video(payload['video_id'])
            rows = sorted(rows, key=lambda row: (-(row['score'] or 0), row['id']))
            ids = [row['id'] for row in rows]
        payload['clip_ids'] = list(ids)[:limit]
    if isinstance(payload.get('montage'),dict) and payload['montage'].get('mirror_main'):
        return _run_mirrored(db,config,job_id,payload,token)
    return _run_without_limit(db, config, job_id, payload, token)
