"""CAN identifiers seen in benign traffic of each vehicle, and how many they share.

The cross-vehicle comparison works because no feature indexes an identifier by
value; this script records how few identifiers the two buses have in common.
"""
import json
import re

from common import CAN_RESULTS
from can_ids.road import AMBIENT, DATA


def road_ids():
    ids = set()
    for f in sorted(AMBIENT.glob('*.log')):
        for line in open(f):
            m = re.search(r' can0 ([0-9A-Fa-f]+)#', line)
            if m:
                ids.add(int(m.group(1), 16))
    return ids


def hcrl_ids():
    ids = set()
    for line in open(DATA / 'hcrl' / 'normal_run_data' / 'normal_run_data.txt'):
        m = re.search(r'ID: ([0-9a-f]+)', line)
        if m:
            ids.add(int(m.group(1), 16))
    return ids


def main():
    road, hcrl = road_ids(), hcrl_ids()
    out = {'road_ambient_ids': len(road), 'hcrl_normal_ids': len(hcrl),
           'shared_ids': len(road & hcrl),
           'shared': [f'0x{i:03x}' for i in sorted(road & hcrl)]}
    print(json.dumps(out, indent=1))
    (CAN_RESULTS / 'id_overlap.json').write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
