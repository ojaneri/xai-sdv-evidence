#!/usr/bin/env python3
"""Smoke tests for the ROAD pipeline.

Cheap checks of the parser, the features and the labels, aimed at the failure
modes that would silently change a result: rejected log lines, non-causal
features, degenerate labels, a wrong timebase, and captures dropped in silence.
Tests that need the ROAD dataset are skipped when it is absent.

Run: make smoke     (or: PYTHONPATH=src python src/smoke_test.py)
"""
import sys
import traceback

import importlib
import json

import numpy as np

from can_ids import features as cf
from can_ids import road as rc

CAP = 'max_speedometer_attack_1'
FAILS = []
SKIPPED = []
HAS_DATA = rc.META.available()


def check(name, fn, needs_data=True):
    """Run one test, record the failure instead of aborting the suite.

    Tests that need the ROAD dataset are SKIPPED, not failed, when it is
    absent: a fresh clone has no data yet, and a wall of failures would hide
    whether the installation itself is sound.
    """
    if needs_data and not HAS_DATA:
        SKIPPED.append(name)
        print(f"  SKIP  {name} (dataset absent)")
        return
    try:
        fn()
        print(f"  PASS  {name}")
    except Exception as e:
        FAILS.append((name, e))
        print(f"  FAIL  {name}: {e}")


def t_parser_reports_rejections():
    """Parser reports rejections."""
    msgs, st = cf.parse_log(rc.ATTACKS / f'{CAP}.log', want_stats=True, limit=5000)
    assert st['total'] > 0, "no lines counted"
    assert st['rejected_frac'] < 0.01, f"{st['rejected_frac']:.2%} rejected"
    assert len(msgs) > 0


def t_features_are_finite():
    """Features are finite."""
    X, _ = rc.load(CAP)
    assert not np.isnan(X).any(), "NaN in features"
    assert not np.isinf(X).any(), "inf in features"


def t_labels_are_not_degenerate():
    """Labels are not degenerate."""
    _, y = rc.load(CAP)
    assert 0 < y.mean() < 1, f"degenerate label distribution: {y.mean()}"


def t_label_rejects_bad_timebase():
    """Label rejects bad timebase."""
    _, _, ts, _ = rc._parsed(CAP)
    try:
        cf.label(ts, (1e9, 2e9), capture='synthetic')
    except ValueError:
        return
    raise AssertionError("label() accepted an interval outside the capture")


def t_precise_label_is_subset_of_window():
    """Every per-frame positive must fall inside the injection window."""
    msgs, _, ts, _ = rc._parsed(CAP)
    iv = rc.META[CAP]['injection_interval']
    yw = cf.label(ts, iv, capture=CAP)
    yp = cf.label_precise(msgs, ts, iv, rc.target_id(CAP),
                          cf.injection_mask(rc.META[CAP]['injection_data_str']))
    assert (yp <= yw).all(), "a per-frame positive lies outside the window"
    assert yp.sum() < yw.sum(), "per-frame labels should be strictly fewer"


def t_fabrication_window_label_is_half_forged():
    """The 50% figure the paper reports must hold, or the claim is stale."""
    msgs, _, ts, ids = rc._parsed('max_speedometer_attack_3')
    iv = rc.META['max_speedometer_attack_3']['injection_interval']
    tid = rc.target_id('max_speedometer_attack_3')
    mask = cf.injection_mask(rc.META['max_speedometer_attack_3']['injection_data_str'])
    yp = cf.label_precise(msgs, ts, iv, tid, mask)
    rel = ts - ts[0]
    inwin = (rel >= iv[0]) & (rel <= iv[1]) & (ids == tid)
    frac = yp[inwin].sum() / inwin.sum()
    assert 0.45 < frac < 0.55, f"forged fraction {frac:.3f}, expected ~0.50"


def t_load_many_refuses_unusable_captures():
    """Load many refuses unusable captures."""
    try:
        rc.load_many(['fuzzing_attack_1'], strict=True)
    except ValueError as e:
        assert 'unusable' in str(e)
        return
    raise AssertionError("load_many silently dropped an unusable capture")


def t_attribution_guard_rejects_zero_mass():
    """Attribution guard rejects zero mass."""
    class Zero:
        def shap_values(self, X):
            """Stub explainer returning zero attribution, for the guard test."""
            return np.zeros_like(X)
    X, _ = rc.load(CAP)
    try:
        rc.normalized_attribution(Zero(), X[:100], n=100)
    except ValueError:
        return
    raise AssertionError("normalized_attribution accepted ~0 mass")


def t_modules_import():
    """Every library module imports (the measurement scripts are not run)."""
    for m in ('common', 'cost.xai_cost', 'cost.xai_cost_vision', 'cost.aggregate_runs',
              'cost.bus_budget', 'can_ids.drift_experiment', 'can_ids.collapse_full',
              'can_ids.sanity_masq', 'can_ids.blindness_check', 'can_ids.cross_vehicle',
              'can_ids.cross_family', 'can_ids.drift_metrics', 'can_ids.ota_drift',
              'can_ids.label_stats', 'can_ids.download_road', 'can_ids.download_hcrl',
              'mcu.analyze', 'mcu.export_model', 'mcu.check_host', 'report.tables'):
        importlib.import_module(m)


def t_saved_results_regenerate():
    """Every table and figure builds from results/ alone."""
    from report.tables import build
    tables, claims = build()
    assert len(tables) == 9 and len(claims) > 50, (len(tables), len(claims))


def t_tabular_aggregation_is_reproducible():
    """aggregate_runs rebuilds tabular_canonical.json from its own per-run medians."""
    from common import COST_RESULTS
    from cost.aggregate_runs import aggregate
    c = json.loads((COST_RESULTS / 'tabular_canonical.json').read_text())
    runs = [{'results': [{'method': m, 'median_ms': v['medians'][i],
                          'model_rows_per_explanation': v['passes']} for m, v in c.items()]}
            for i in range(len(next(iter(c.values()))['medians']))]
    assert aggregate(runs) == c


NO_DATA = {'modules_import', 'saved_results_regenerate',
           'tabular_aggregation_is_reproducible'}


def t_extract_is_causal():
    """Truncating the stream must not change earlier rows."""
    msgs = cf.parse_log(rc.ATTACKS / f'{CAP}.log', limit=4000)
    full, _ = cf.extract(msgs)
    part, _ = cf.extract(msgs[:2000])
    assert np.allclose(full[:2000], part, equal_nan=True), \
        "feature rows depend on future messages"


if __name__ == '__main__':
    print("ROAD pipeline smoke tests")
    if not HAS_DATA:
        print("  (ROAD dataset not found -- data-dependent tests are skipped;\n"
              "   fetch it with: make data-road)\n")
    for name, fn in sorted(globals().items()):
        if name.startswith('t_'):
            check(name[2:], fn, needs_data=name[2:] not in NO_DATA)
    print(f"\n{len(FAILS)} failure(s), {len(SKIPPED)} skipped")
    sys.exit(1 if FAILS else 0)
