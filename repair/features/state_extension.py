"""Durable clip originals that survive changes to clip IDs."""
import json as _oj
import shutil as _ocopy
import uuid as _ouuid
import threading as _othread
from pathlib import Path as _OPath
from datetime import datetime as _OTime,timezone as _OTZ
from contextvars import ContextVar as _OCV
_original_context=_OCV('clip_original_origin',default=None)
_original_lock=_othread.RLock()

def _original_tables(db):
    db.conn.execute('CREATE TABLE IF NOT EXISTS clip_initial_states (origin TEXT PRIMARY KEY, row_json TEXT NOT NULL, file_path TEXT NOT NULL, captured_at TEXT NOT NULL, kind TEXT NOT NULL)')
    db.conn.execute('CREATE TABLE IF NOT EXISTS clip_initial_map (clip_id INTEGER PRIMARY KEY, origin TEXT NOT NULL)')
    db.conn.commit()

def original_snapshot(db,clip_id,kind='existing'):
    with _original_lock:
        _original_tables(db)
        saved=db.conn.execute('SELECT s.* FROM clip_initial_states s JOIN clip_initial_map m ON s.origin=m.origin WHERE m.clip_id=?',(clip_id,)).fetchone()
        if saved is not None:return dict(saved)
        row=db.get_clip(clip_id)
        if row is None:raise ValueError('Клип не найден')
        row=dict(row);source=_OPath(row.get('path') or '')
        if not source.is_file():raise ValueError('Файл клипа отсутствует: сохранить оригинал невозможно')
        origin=_ouuid.uuid4().hex
        data=_OPath(db.conn.execute('PRAGMA database_list').fetchone()[2]).parent
        folder=data/'clip-originals'/origin;folder.mkdir(parents=True,exist_ok=False)
        destination=folder/('original'+source.suffix);_ocopy.copyfile(source,destination)
        saved={'origin':origin,'row_json':_oj.dumps(row,ensure_ascii=False),'file_path':str(destination),'captured_at':_OTime.now(_OTZ.utc).isoformat(),'kind':kind}
        (folder/'original.json').write_text(_oj.dumps(saved,ensure_ascii=False,indent=2),encoding='utf8')
        db.conn.execute('INSERT INTO clip_initial_states VALUES (?,?,?,?,?)',tuple(saved[k] for k in ('origin','row_json','file_path','captured_at','kind')))
        db.conn.execute('INSERT INTO clip_initial_map VALUES (?,?)',(clip_id,origin));db.conn.commit()
        return saved

def restore_original(db,clip_id):
    with _original_lock:
        saved=original_snapshot(db,clip_id);initial=_oj.loads(saved['row_json'])
        current=db.get_clip(clip_id)
        if current is None:raise ValueError('Клип не найден')
        current=dict(current)
        collision=db.conn.execute('SELECT id FROM clips WHERE video_id=? AND start_s=? AND end_s=? AND id<>?',(initial['video_id'],initial['start_s'],initial['end_s'],clip_id)).fetchone()
        if collision is not None:raise ValueError('Другой клип уже занимает исходные границы; откат остановлен, чтобы не затронуть его')
        backup=_OPath(saved['file_path'])
        if not backup.is_file():raise ValueError('Сохранённая первоначальная версия отсутствует')
        current_path=_OPath(current.get('path') or '')
        if current_path.is_file():
            _ocopy.copyfile(current_path,backup.parent/('before-last-restore'+current_path.suffix))
            (backup.parent/'before-last-restore.json').write_text(_oj.dumps(current,ensure_ascii=False,indent=2),encoding='utf8')
        destination=_OPath(initial['path']).with_name(f'restored_{clip_id}_{saved["origin"][:12]}{backup.suffix}')
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_name(destination.name+'.tmp');_ocopy.copyfile(backup,temporary);temporary.replace(destination)
        fields=[k for k in ('start_s','end_s','score','hook','render_opts','title','description','hashtags','scores') if k in initial and k in current]
        db.conn.execute('UPDATE clips SET '+','.join(k+'=?' for k in fields)+',path=? WHERE id=?',[initial[k] for k in fields]+[str(destination),clip_id]);db.conn.commit()
        return dict(db.get_clip(clip_id))

_add_clip_before_original=StateDB.add_clip
def _add_clip_with_original(self,*args,**kwargs):
    clip_id=_add_clip_before_original(self,*args,**kwargs)
    if clip_id is not None:
        origin=_original_context.get()
        if origin:
            _original_tables(self);self.conn.execute('INSERT OR REPLACE INTO clip_initial_map VALUES (?,?)',(clip_id,origin));self.conn.commit()
        else:
            row=self.get_clip(clip_id)
            if row is not None and _OPath(row['path'] or '').is_file():original_snapshot(self,clip_id,'created')
    return clip_id
StateDB.add_clip=_add_clip_with_original
