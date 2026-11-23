"""Source-range controls use the existing render queue and caption refitting."""
import math
from pydantic import BaseModel, Field

class SourceRangeIn(BaseModel):
    start: float = Field(ge=0,allow_inf_nan=False)
    end: float = Field(gt=0,allow_inf_nan=False)

def _source_range_info(config,clip_id):
    from video_editor.montage_render import probe
    data=Path(config['paths']['data_dir'])
    database=StateDB(data/'state.db')
    try:
        row=database.get_clip(clip_id)
        if row is None: raise HTTPException(404,'Клип не найден')
        row=dict(row)
    finally: database.close()
    source=data/'downloads'/f"{row['video_id']}.mp4"
    if not source.is_file():
        raise HTTPException(409,'Исходное видео отсутствует. Восстановите его в библиотеке, чтобы расширить клип.')
    duration=probe(source)['duration']
    if not math.isfinite(duration) or duration<=0: raise HTTPException(409,'Не удалось определить длительность исходника')
    return row,{'clip_id':clip_id,'start':row['start_s'],'end':row['end_s'],
        'source_duration':duration,'available_before':max(0,row['start_s']),
        'available_after':max(0,duration-row['end_s'])}

def _range_edit(edit,old_start,old_end,new_start,new_end):
    """Shift existing edits and include newly requested material on both ends."""
    import copy
    if not edit: return None
    result=copy.deepcopy(edit)
    shift=old_start-new_start
    duration=new_end-new_start
    def spans(items):
        out=[]
        for a,b in items:
            a,b=max(0,float(a)+shift),min(duration,float(b)+shift)
            if b>a: out.append([round(a,3),round(b,3)])
        return out
    keep=spans(edit.get('keep') or [[0,old_end-old_start]])
    if new_start<old_start: keep.append([0,old_start-new_start])
    if new_end>old_end: keep.append([old_end-new_start,duration])
    merged=[]
    for a,b in sorted(keep):
        if merged and a<=merged[-1][1]+0.001: merged[-1][1]=max(b,merged[-1][1])
        else: merged.append([a,b])
    if not merged: raise HTTPException(400,'Выбранный диапазон полностью вырезан сохранённым монтажом')
    result['keep']=merged
    result['mutes']=spans(edit.get('mutes',[]))
    words=[]
    for word in edit.get('muted_words',[]):
        if isinstance(word,dict):
            item=dict(word); item['start']=max(0,float(item['start'])+shift);item['end']=min(duration,float(item['end'])+shift)
            if item['end']>item['start']: words.append(item)
        elif isinstance(word,(list,tuple)) and len(word)==2: words.extend(spans([word]))
    result['muted_words']=words
    return result

def install_source_range(app,config,render_endpoint):
    from core.state import original_snapshot,restore_original
    def original_db():return StateDB(Path(config['paths']['data_dir'])/'state.db')
    @app.get('/clips/{clip_id}/original-state')
    def get_original_state(clip_id:int):
        database=original_db()
        try:
            saved=original_snapshot(database,clip_id);row=json.loads(saved['row_json'])
            return {'available':True,'kind':saved['kind'],'captured_at':saved['captured_at'],'start':row['start_s'],'end':row['end_s']}
        except ValueError as e:return {'available':False,'reason':str(e)}
        finally:database.close()
    @app.post('/clips/{clip_id}/restore-original')
    def restore_original_state(clip_id:int):
        database=original_db()
        try:
            for job in database.conn.execute("SELECT payload FROM jobs WHERE type='render' AND status IN ('queued','running')"):
                if json.loads(job['payload']).get('clip_id')==clip_id:raise HTTPException(409,'Дождитесь завершения обработки клипа перед откатом')
            row=restore_original(database,clip_id)
            return {'restored':True,'clip_id':clip_id,'start':row['start_s'],'end':row['end_s']}
        except ValueError as e:raise HTTPException(409,str(e)) from e
        finally:database.close()
    @app.get('/clips/{clip_id}/source-range')
    def get_source_range(clip_id:int):
        return _source_range_info(config,clip_id)[1]

    @app.post('/clips/{clip_id}/source-range')
    def change_source_range(clip_id:int,body:SourceRangeIn):
        row,info=_source_range_info(config,clip_id)
        if body.end<=body.start: raise HTTPException(400,'Конец должен быть позже начала')
        if body.end>info['source_duration']+0.001:
            raise HTTPException(400,'Конец выходит за границы исходного видео')
        if body.start>=info['source_duration']:
            raise HTTPException(400,'Начало выходит за границы исходного видео')
        options=json.loads(row.get('render_opts') or '{}')
        if options.get('reel'): raise HTTPException(400,'Сборный ролик нельзя расширить как один фрагмент исходника')
        new_edit=_range_edit(options.get('edit'),row['start_s'],row['end_s'],body.start,body.end)
        result=render_endpoint(clip_id,RenderIn(start=body.start,end=min(body.end,info['source_duration']),render_opts={'edit':new_edit}))
        return {**result,'start':body.start,'end':body.end,'source_duration':info['source_duration']}

_create_app_before_range=create_app
def create_app(config,settings_path):
    app=_create_app_before_range(config,settings_path)
    route=next(route for route in app.routes if getattr(route,'path',None)=='/clips/{clip_id}/render')
    install_source_range(app,config,route.endpoint)
    from core.state import original_snapshot
    database=StateDB(Path(config['paths']['data_dir'])/'state.db')
    try:
        for row in database.conn.execute('SELECT id,path FROM clips WHERE path IS NOT NULL').fetchall():
            if Path(row['path']).is_file():original_snapshot(database,row['id'],'existing')
    finally:database.close()
    return app
