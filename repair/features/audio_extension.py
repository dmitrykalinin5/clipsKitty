"""Mute only requested intervals, with sample-level 5ms ramps inside edges."""
def mute_filter(mutes):
    gates=[]
    for start,end in mutes:
        start,end=float(start),float(end)
        if end<=start:continue
        fade=min(0.005,(end-start)/4)
        # No padding beyond the interval: neighboring phonemes stay untouched.
        gates.append(f'(clip(({start+fade:.6f}-t)/{fade:.6f},0,1)+clip((t-{end-fade:.6f})/{fade:.6f},0,1))')
    return "aeval=exprs='val(ch)*"+'*'.join(gates)+"':c=same" if gates else ''
