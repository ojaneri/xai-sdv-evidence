#!/usr/bin/env python3
"""Check the regenerated tables and figures against the numbers in the paper.

The expected values below are transcribed from the paper's LaTeX sources
(tables, figure coordinates and numbers quoted in the text). Every table cell
is compared as printed; every number quoted in the text is compared within
half a unit of its last printed digit.

A few differences are presentation choices in the paper (a range printed as one
value, a truncated range end); they are listed in NOTED with the reason and
reported as NOTE, not as failures.

    python -m report.check_paper       # exit status 1 on any unexplained mismatch
"""
import sys

from report.tables import build

# ------------------------------------------------------------------ tables
# Value cells only (the first column, regime or row label, is not compared).
EXPECTED_TABLES = {
    'tab_cost': [
        ['inference only', '0.28 ms', '0.46 ms', '2.8%', '1'],
        ['TreeSHAP (exact)', '0.82 ms', '0.98 ms', '8.2%', '0'],
        ['LIME', '61.6 ms', '71.4 ms', '616%', '5,000'],
        ['KernelSHAP', '633 ms', '622 ms', '6,327%', '209,601'],
        ['inference only', '63.3 ms', '85.6 ms', '63%', '1'],
        ['Grad-CAM', '78.5 ms', '100 ms', '78%', '1'],
        ['Integrated Gradients (50)', '7,934 ms', '8,324 ms', '7,934%', '50'],
        ['Occlusion (stride 16)', '10,834 ms', '11,193 ms', '10,834%', '170'],
    ],
    'fig_cost_model': [
        ['50', '1.3', ''], ['170', '3.3', ''], ['626', '4.1', ''],
        ['5', '2.2', 'calibration'], ['10', '1.5', ''], ['20', '22.7', ''], ['50', '42.5', ''],
    ],
    'tab_platforms': [
        ['1', '0.28 ms', '0.25 ms', '0.71 ms', '1.39 ms'],
        ['0', '0.82 ms', '0.70 ms', '166 ms', '520 ms'],
        ['25', '---', '---', '17.9 ms', '37.3 ms'],
        ['5,000', '61.6 ms', '49.0 ms', '3.81 s', '8.64 s'],
        ['209,601', '633 ms', '535 ms', '138 s', '318 s'],
    ],
    'tab_collapse': [
        ['3', '1.000', '0.000'],
        ['4', '0.000', '0.011'],
        ['', '0.504', '0.000'],
        ['', '59.0%', ''],
        ['', '71.2%', ''],
        ['', '100%', '0%'],
        ['', '0.229', ''],
        ['3 / 4', '0.998 / 0.999', '0.000 / 0.001'],
    ],
    'fig_collapse': [
        ['0xd0', '1.000', '0.000'], ['0xd0', '1.000', '0.001'], ['0xd0', '1.000', '0.000'],
        ['0x4e7', '0.816', '0.130'], ['0x6e0', '0.000', '0.003'], ['0x6e0', '0.000', '0.019'],
        ['0x6e0', '0.000', '0.000'],
    ],
    'fig_attribution': [
        ['59.0', '51.7'], ['10.2', '9.0'], ['7.0', '17.4'], ['6.9', '6.0'], ['4.7', '4.6'],
        ['2.6', '2.3'], ['2.1', '0.9'], ['1.7', '1.3'], ['0.229', ''],
    ],
    'tab_transfer': [
        ['=', '=', '1.000', '1.000', '0.0000'],
        ['=', '=', '0.999', '1.000', '0.0000'],
        ['!=', '=', '0.000', '0.000', '0.1792'],
        ['!=', '=', '0.198', '0.110', '0.0001'],
        ['=', '!=', '0.000', '0.000', '0.0001'],
        ['!=', '!=', '0.003', '0.012', '0.1831'],
        ['!=', '=', '0.001', '0.000', '0.0005'],
        ['!=', '=', '0.347', '0.210', '0.0000'],
        ['!=', '=', '0.104', '1.000', '0.1933'],
        ['!=', '=', '0.000', '0.000', '0.0000'],
        ['', '', '51.0%', '50%', '46%'],
        ['', '', '19.9%', '19%', '78%'],
    ],
    'tab_driftmetrics': [
        ['0.103', '0.471', '0.181', '0.286', '0.070', '0.223'],
        ['0.154', '0.274', '0.120', '0.137', '0.154', '0.205'],
        ['0.522', '0.957', '0.589', '0.994', '0.688', '0.598'],
        ['0.060', '0.410', '0.344', '0.418', '0.086', '0.265'],
        ['0.870', '1.000', '0.935', '0.999', '0.960', '0.980'],
        ['0.873', '1.000', '0.916', '0.996', '0.993', '0.966'],
        ['0.173', '0.527', '0.330', '0.737', '0.463', '0.311'],
    ],
    'tab_ota': [
        ['1.000', '0.667', '0.000', '---', 'bytes_changed (0.59)'],
        ['1.000', '0.666', '0.000', '0.036-0.047', 'bytes_changed (0.59)'],
        ['0.991', '0.662', '0.966', '0.93', 'bytes_changed (0.23)'],
        ['0.666', '0.999', '0.000', '1.15', 'id_count_win (0.58)'],
    ],
}

# ------------------------------------------------------------------ text
# id -> (value printed in the paper, tolerance). Tolerance is half a unit of
# the last printed digit unless the paper states a bound.
EXPECTED_CLAIMS = {
    'bus.road_captures': (12, 0),
    'bus.frames': (2.5e7, 0.05e7),
    'bus.id_fast_min': (9.7, 0.05),
    'bus.id_fast_max': (10.0, 0.05),
    'bus.road_mean_gap': (0.42, 0.005),
    'bus.hcrl_mean_gap': (0.51, 0.005),
    'bus.road_peak_gap': (0.23, 0.005),
    'cost.tree_pct_budget': (8.2, 0.05),
    'cost.kernel_x_budget': (63, 0.5),
    'cost.tree_x_bus_gap': (2, 0.1),          # "twice the mean gap"
    'cost.tree_x_inference': (2.9, 0.05),
    'cost.cv_min': (8, 0.5),
    'cost.cv_max': (13, 0.5),
    'cost.ratio_spread_min': (35, 0.5),
    'cost.ratio_spread_max': (58, 0.5),
    'cost.gradcam_n400_median': (85.7, 0.05),
    'cost.gradcam_n400_p99': (205, 0.5),
    'arm.pred_median_err': (3.5, 0.05),
    'arm.pred_max_err': (7.0, 0.05),
    'arm.occl_max_err': (2.7, 0.05),
    'arm.ig_min_err': (-7.0, 0.05),
    'x86.ig_max_err': (42.5, 0.05),
    'x86.ig_batch_growth_min': (22, 0.5),
    'x86.ig_batch_growth_max': (39, 0.5),
    'arm.latency_move_min': (12, 0.5),
    'arm.latency_move_max': (20, 0.5),
    'arm.passes_identical': (1, 0),
    'mcu.max_err_margin': (4e-6, 0.5e-6),
    'mcu.max_err_treeshap': (2e-6, 0.5e-6),
    'mcu.checked_samples': (16, 0),
    'mcu.nrf.tree_x_deadline': (17, 0.5),
    'mcu.nrf.tree_x_inference': (232, 0.5),
    'mcu.nrf.kernel_x_tree': (830, 5),
    'mcu.nrf.eq1_err_min': (-5.6, 0.05),
    'mcu.nrf.eq1_err_max': (9.4, 0.05),
    'mcu.nrf.eq1_same_method_err': (-1.3, 0.05),
    'mcu.stm.tree_x_deadline': (52, 0.5),
    'mcu.stm.tree_x_inference': (375, 0.5),
    'mcu.stm.kernel_x_tree': (610, 5),
    'mcu.stm.eq1_err_min': (9.8, 0.05),
    'mcu.stm.eq1_err_max': (27.3, 0.05),
    'mcu.stm.eq1_same_method_err': (-1.4, 0.05),
    'mcu.cv_max': ('<', 0.1),                 # "below 0.1%"
    'mcu.l475_vs_l476_max_cycles': ('<', 100),  # "within 100 cycles"
    'mcu.kernel_cycles_stm': (5.08e9, 0.005e9),
    'mcu.power_min': (56.6, 0.05),
    'mcu.power_max': (60.6, 0.05),
    'mcu.power_idle': (61.3, 0.05),
    'mcu.energy_tree': (9.3, 0.05),
    'mcu.energy_kernel': (8.2, 0.05),
    'can.window_benign_min': (50, 0.5),
    'can.window_benign_max': (50, 0.5),
    'can.masq_flagged': (2, 0),
    'can.masq_n': (20895, 0),
    'can.masq_true_rate': (52.1, 0.05),
    'can.masq_trained_f1': (0.966, 0.0005),
    'can.masq_trained_payload': (99.7, 0.05),
    'can.attr_magnitude_ratio': (0.97, 0.005),
    'can.bytes_changed_fab': (59.0, 0.05),
    'can.bytes_changed_mas': (51.7, 0.05),
    'can.blindness_margin': (-0.644, 0.0005),
    'can.prev_road_min': (1.5, 0.05),
    'can.prev_road_max': (2.9, 0.05),
    'can.prev_hcrl_min': (17.2, 0.05),
    'can.prev_hcrl_max': (21.4, 0.05),
    'can.family_within_min': (0.991, 0.0005),
    'can.family_timing_hcrl_spoof': (88, 0.5),
    'can.family_timing_hcrl_fuzz': (56, 0.5),
    'can.family_timing_road_spoof': (20, 0.5),
    'can.family_timing_road_fuzz': (3, 0.5),
    'can.mmd_benign_max_trainref': (0.410, 0.0005),
    'can.mmd_collapse_min_trainref': (0.344, 0.0005),
    'can.mmd_collapse_min_benignref': (0.055, 0.0005),
    'can.mmd_collapse_max_benignref': (0.086, 0.0005),
    'can.mmd_fab_min_benignref': (0.265, 0.0005),
    'can.mmd_fab_max_benignref': (0.499, 0.0005),
}

# Differences that are presentation choices in the paper, not reproduction
# failures. Key: table name and (row, column) of the value cells, or claim id.
NOTED = {
    ('tab_ota', 1, 1): 'the two retrainings give 0.6666 and 0.6665; the paper prints the range as 0.666',
    ('tab_ota', 1, 4): 'the two retrainings give shares 0.590 and 0.598; the paper prints the range as 0.59',
    'mcu.nrf.eq1_err_min': 'KernelSHAP N=21,001 errs by -5.65% (N=209,601: -5.64%); the paper prints -5.6',
}


def main():
    tables, claims = build()
    ok = noted = bad = 0
    for name, exp in EXPECTED_TABLES.items():
        rows = [r[1:] for r in tables[name]['rows']]
        if len(rows) != len(exp):
            print(f"FAIL  {name}: {len(rows)} rows regenerated, {len(exp)} in the paper")
            bad += 1
            continue
        for i, (got, want) in enumerate(zip(rows, exp)):
            for j, (g, w) in enumerate(zip(got, want)):
                if g == w:
                    ok += 1
                elif (name, i, j) in NOTED:
                    noted += 1
                    print(f"NOTE  {name} row {i + 1} col {j + 2}: regenerated {g!r}, paper {w!r} "
                          f"-- {NOTED[(name, i, j)]}")
                else:
                    bad += 1
                    print(f"FAIL  {name} row {i + 1} col {j + 2}: regenerated {g!r}, paper {w!r}")
    byid = {c['id']: c for c in claims}
    for cid, (want, tol) in EXPECTED_CLAIMS.items():
        v = byid[cid]['value']
        if want == '<':
            good = v < tol
            desc = f"< {tol}"
        else:
            good = abs(v - want) <= tol + 1e-12
            desc = f"{want} +/- {tol}"
        if good:
            ok += 1
        elif cid in NOTED:
            noted += 1
            print(f"NOTE  {cid}: regenerated {v:.6g}, paper {desc} -- {NOTED[cid]}")
        else:
            bad += 1
            print(f"FAIL  {cid}: regenerated {v:.6g}, paper {desc} ({byid[cid]['text']})")
    print(f"\n{ok} values match the paper, {noted} noted presentation differences, {bad} mismatches")
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
