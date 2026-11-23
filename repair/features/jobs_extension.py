from core.state import original_snapshot,_original_context
_rerender_before_original=Worker._rerender_clip
def _rerender_with_original(self,db,payload):
    saved=original_snapshot(db,payload['clip_id'])
    handle=_original_context.set(saved['origin'])
    try:return _rerender_before_original(self,db,payload)
    finally:_original_context.reset(handle)
Worker._rerender_clip=_rerender_with_original
