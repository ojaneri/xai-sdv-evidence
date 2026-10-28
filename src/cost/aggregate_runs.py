#!/usr/bin/env python3
"""Combine several runs of cost.xai_cost into results/cost/tabular_canonical.json.

Tabular latencies vary 8-13% between runs on a shared server, so the paper
reports, per method, the median of the per-run medians. Per method:

  medians            per-run median latency (ms), in the order the runs are given
  median_of_medians  the figure reported in the paper
  cv_pct             population coefficient of variation of the per-run medians
  passes             model rows per explanation (identical in every run)
  ratio_range        [min, max] over runs of (method median / inference median)

    python -m cost.aggregate_runs results/cost/runs/tabular_run*.json
"""
import argparse
import json
import statistics as st
from pathlib import Path

from common import COST_RESULTS

BASE = "inference only (no XAI)"


def aggregate(runs):
    """runs: list of xai_cost.py outputs (dicts). Returns the canonical dict."""
    per = [{r["method"]: r for r in run["results"]} for run in runs]
    out = {}
    for method in per[0]:
        meds = [p[method]["median_ms"] for p in per]
        passes = {p[method]["model_rows_per_explanation"] for p in per}
        if len(passes) != 1:
            raise ValueError(f"{method}: pass count differs between runs: {passes}")
        ratios = [p[method]["median_ms"] / p[BASE]["median_ms"] for p in per]
        out[method] = {
            "medians": meds,
            "median_of_medians": st.median(meds),
            "cv_pct": round(100 * st.pstdev(meds) / st.mean(meds), 1),
            "passes": passes.pop(),
            "ratio_range": [round(min(ratios), 2), round(max(ratios), 2)],
        }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("runs", nargs="+", help="tabular JSON files written by cost.xai_cost")
    ap.add_argument("--out", default=str(COST_RESULTS / "tabular_canonical.json"))
    a = ap.parse_args()
    runs = [json.loads(Path(p).read_text()) for p in a.runs]
    out = aggregate(runs)
    Path(a.out).write_text(json.dumps(out, indent=2))
    for m, r in out.items():
        print(f"{m:<32} median {r['median_of_medians']:>10.4f} ms  CV {r['cv_pct']:>5.1f}%  "
              f"passes {r['passes']:>7}  ratio {r['ratio_range']}")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
