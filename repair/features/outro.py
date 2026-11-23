"""Compatibility entry points for exports; branded end cards are removed.

Only the generic file replacement helpers are retained from the old module,
because preview and user-supplied watermark exports also use those helpers.
"""
import os
import time
import shutil
from pathlib import Path

DURATION = 0.0

def enabled(config):
    return False

def append(clip, config):
    return False

def reset_tally():
    pass

def summary():
    return ''

def has_outro(clip, window_seconds):
    return False

def backfill(db, config, video_id=None):
    return {'added': 0, 'already': 0, 'failed': 0}

def _overwrite_in_place(src, dst):
    # The build script preserves the original generic helper here.
    raise NotImplementedError

def _replace_with_retry(src, dst, budget=10.0, label='Export'):
    # The build script preserves the original generic helper here.
    raise NotImplementedError

def finish(src, dst, config):
    src, dst = Path(src).resolve(), Path(dst).resolve()
    if src != dst:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not _replace_with_retry(src, dst, label='Export'):
            raise OSError(f'Could not write export: {dst}')
    return False
