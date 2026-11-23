"""Preserve and validate the per-job clip count alongside template settings."""
_snapshot_without_limit = snapshot

def snapshot(data_dir, choice):
    limit = choice.get('clip_limit') if isinstance(choice, dict) else None
    if limit is not None and (type(limit) is not int or limit < 1):
        raise HTTPException(400, 'Количество клипов должно быть целым числом больше нуля')
    clean_choice = {k: v for k, v in choice.items() if k != 'clip_limit'} if isinstance(choice, dict) else choice
    result = _snapshot_without_limit(data_dir, clean_choice)
    if isinstance(result, dict) and limit is not None:
        result['clip_limit'] = limit
    return result
