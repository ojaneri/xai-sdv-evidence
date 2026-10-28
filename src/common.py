"""Paths shared by every script in this repository.

The datasets live under data/ at the repository root unless the environment
variable XAI_SDV_DATA points elsewhere (useful when one copy of ROAD and HCRL is
shared by several checkouts). Results are written under results/<topic>/.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('XAI_SDV_DATA', ROOT / 'data')).resolve()
RESULTS = ROOT / 'results'
COST_RESULTS = RESULTS / 'cost'
CAN_RESULTS = RESULTS / 'can'
MCU_RESULTS = RESULTS / 'mcu'
