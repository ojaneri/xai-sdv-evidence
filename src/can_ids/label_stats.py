#!/usr/bin/env python3
"""How wrong is the window label, and why does bytes_changed work?

For each held-out matched pair, restricted to the attacked CAN ID inside the
injection interval:

  forged fraction  frames that match ROAD's injection mask / all frames.
                   Under fabrication the legitimate frames keep flowing, so a
                   window label marks the remainder (about half) as attacks.
  alternation      fraction of consecutive frame pairs whose per-frame labels
                   differ. Fabrication interleaves forged and legitimate frames
                   (forged, legit, forged, ...); masquerade replaces the
                   legitimate frames, so forged frames run consecutively.

The labels are those of road.load(precise=True); nothing is trained here.

    python -m can_ids.label_stats       # writes results/can/label_stats.json
"""
import json

import numpy as np

from can_ids import features as cf
from can_ids import road as rc
from can_ids.drift_experiment import TEST_FAB, TEST_MAS


def stats(name):
    """Forged fraction and label alternation for one capture."""
    msgs, _, ts, ids = rc._parsed(name)
    iv = rc.META[name]['injection_interval']
    tid = rc.target_id(name)
    mask = cf.injection_mask(rc.META[name]['injection_data_str'])
    y = cf.label_precise(msgs, ts, iv, tid, mask, capture=name)
    rel = ts - ts[0]
    inwin = (rel >= iv[0]) & (rel <= iv[1]) & (ids == tid)
    yw = y[inwin]
    pairs = len(yw) - 1
    flips = int((yw[1:] != yw[:-1]).sum())
    return {'capture': name, 'target_id': hex(tid),
            'frames_in_window': int(inwin.sum()), 'forged': int(yw.sum()),
            'forged_frac': float(yw.mean()),
            'pairs': int(pairs), 'alternating_pairs': flips,
            'alternation': float(flips / pairs) if pairs else float('nan')}


def main():
    out = {'fabrication': [], 'masquerade': []}
    for kind, names in (('fabrication', TEST_FAB), ('masquerade', TEST_MAS)):
        for n in names:
            r = stats(n)
            out[kind].append(r)
            print(f"{kind:<12} {n:<40} in window {r['frames_in_window']:>6}  "
                  f"forged {r['forged']:>6} ({r['forged_frac']*100:5.1f}%)  "
                  f"alternation {r['alternating_pairs']:>6}/{r['pairs']:<6} "
                  f"({r['alternation']*100:5.1f}%)", flush=True)
    p = rc.CAN_RESULTS / 'label_stats.json'
    p.write_text(json.dumps(out, indent=1))
    print(f"-> {p.relative_to(rc.ROOT)}")


if __name__ == '__main__':
    main()
