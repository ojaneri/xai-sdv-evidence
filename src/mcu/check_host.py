#!/usr/bin/env python3
"""Compare the host build of xai_core.c (host_check) with the shap reference.

    ./build/host_check > build/host_out.json
    python -m mcu.check_host build/host_out.json

Checks margins and exact TreeSHAP values of the 16 embedded test samples
against results/mcu/ref.json, and prints the pass counts of each method.
"""
import json
import sys

import numpy as np

from common import MCU_RESULTS


def main():
    host = json.load(open(sys.argv[1]))
    ref = json.load(open(MCU_RESULTS / 'ref.json'))
    em = float(np.max(np.abs(np.array(host['margin']) - np.array(ref['margin']))))
    ep = float(np.max(np.abs(np.array(host['phi']) - np.array(ref['phi']))))
    print(f"max |margin - ref|   = {em:.2e}")
    print(f"max |TreeSHAP - ref| = {ep:.2e}")
    print(f"passes: TreeSHAP {host['passes_tree']}, occlusion {host['passes_occl']}, "
          f"LIME {host['passes_lime']}, KernelSHAP {host['passes_kernel']}")
    ok = em < 1e-4 and ep < 1e-4
    print("OK" if ok else "MISMATCH")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
