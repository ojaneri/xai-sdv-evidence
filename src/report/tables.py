#!/usr/bin/env python3
"""Regenerate every table and figure of the paper from the saved results.

Reads only results/ (no dataset, no model training) and prints each table and
figure as text, in the paper's units and rounding. The same values are written
to out/<name>.txt and out/paper_numbers.json, and checked against the numbers
printed in the paper by report.check_paper.

    python -m report.tables            # all tables and figures
    python -m report.tables tab_cost   # one of them
"""
import json
import re
import statistics as st
import sys
from pathlib import Path

from common import ROOT, COST_RESULTS, CAN_RESULTS, MCU_RESULTS

OUT = ROOT / 'out'


def load(path):
    return json.loads(Path(path).read_text())


# ------------------------------------------------------------- formatting
def ms(x):
    """Latency in ms with the paper's precision: 0.28, 1.39, 61.6, 633, 7,934."""
    if x < 10:
        return f"{x:.2f} ms"
    if x < 100:
        return f"{x:.1f} ms"
    return f"{x:,.0f} ms"


def ms_or_s(x):
    """MCU latency: ms below one second, seconds above (3.81 s, 138 s)."""
    if x < 1000:
        return ms(x)
    s = x / 1000
    return f"{s:.2f} s" if s < 10 else f"{s:.0f} s"


def f3(x):
    return f"{x:.3f}"


def f4(x):
    return f"{x:.4f}"


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def rng(a, b, fmt=f3):
    """A range, collapsed to one value when both ends print the same."""
    lo, hi = fmt(min(a, b)), fmt(max(a, b))
    return lo if lo == hi else f"{lo}-{hi}"


TABLES = {}
CLAIMS = []


def table(name, title, sources):
    def deco(fn):
        TABLES[name] = (title, sources, fn)
        return fn
    return deco


def claim(cid, text, value, source, unit=''):
    CLAIMS.append({'id': cid, 'text': text, 'value': value, 'unit': unit, 'source': source})


# ------------------------------------------------------------- cost
METHODS_TAB = [("inference only", "inference only (no XAI)"),
               ("TreeSHAP (exact)", "SHAP (Tree, exact)"),
               ("LIME", "LIME"),
               ("KernelSHAP", "SHAP (Kernel, model-agnostic)")]


@table('tab_cost', 'Table: cost of one explanation on the server (x86 EPYC, single-threaded)',
       ['results/cost/tabular_canonical.json', 'results/cost/tabular_x86_p99.json',
        'results/cost/vision.json', 'results/cost/vision_n400.json',
        'results/cost/gradcam_boundary.json'])
def tab_cost():
    canon = load(COST_RESULTS / 'tabular_canonical.json')
    p99 = load(COST_RESULTS / 'tabular_x86_p99.json')['p99_ms']
    vis = {r['method']: r for r in load(COST_RESULTS / 'vision.json')['results']}
    n400 = {r['method']: r for r in load(COST_RESULTS / 'vision_n400.json')['results']}
    rows = []
    for label, key in METHODS_TAB:
        c = canon[key]
        rows.append(['Tabular', label, ms(c['median_of_medians']), ms(p99[key]),
                     f"{100 * c['median_of_medians'] / 10.0:,.1f}%" if c['median_of_medians'] < 10
                     else f"{100 * c['median_of_medians'] / 10.0:,.0f}%",
                     f"{c['passes']:,}"])
    perc = [("inference only", "inference only (no XAI)"),
            ("Grad-CAM", "Grad-CAM"),
            ("Integrated Gradients (50)", "Integrated Gradients (50 steps)"),
            ("Occlusion (stride 16)", "Occlusion (32x32 stride 16)")]
    for label, key in perc:
        v = vis[key]
        p = v['p99_ms']  # every perception row from the same run
        rows.append(['Perception', label, ms(v['median_ms']), ms(p),
                     f"{v['median_ms']:,.0f}%", f"{n400[key]['images_per_explanation']:,}"])
    return ['Regime', 'Method', 'Median', 'p99', '% of budget', 'Passes'], rows


@table('fig_cost_model', 'Figure: prediction error of T = N t_pass(N) vs passes (x86)',
       ['results/cost/model_validation.json'])
def fig_cost_model():
    mv = load(COST_RESULTS / 'model_validation.json')
    rows = [[r['family'], str(r['images']), f"{r['error_pct']:.1f}",
             'calibration' if r.get('calibration') else ''] for r in mv['rows']]
    return ['Family', 'Passes N', 'Error %', ''], rows


@table('tab_platforms', 'Table: the same explanation on four processors',
       ['results/cost/tabular_canonical.json', 'results/cost/arm-neoverse-v1/tabular_c7g.json',
        'results/mcu/xai-nrf52840-r1/analysis.json', 'results/mcu/xai-nucleo-l476rg/analysis.json'])
def tab_platforms():
    canon = load(COST_RESULTS / 'tabular_canonical.json')
    arm = {r['method']: r for r in load(COST_RESULTS / 'arm-neoverse-v1/tabular_c7g.json')['results']}
    nrf = load(MCU_RESULTS / 'xai-nrf52840-r1/analysis.json')['ops']
    stm = load(MCU_RESULTS / 'xai-nucleo-l476rg/analysis.json')['ops']
    spec = [("inference only", "inference only (no XAI)", 'infer_test'),
            ("TreeSHAP (exact)", "SHAP (Tree, exact)", 'treeshap'),
            ("Occlusion", None, 'occlusion'),
            ("LIME", "LIME", 'lime5000'),
            ("KernelSHAP", "SHAP (Kernel, model-agnostic)", 'kernel2096')]
    rows = []
    for label, key, op in spec:
        passes = {int(nrf[op]['passes_per_rep'][0]), int(stm[op]['passes_per_rep'][0])}
        if key:
            passes |= {canon[key]['passes'], arm[key]['model_rows_per_explanation']}
        assert len(passes) == 1, (label, passes)
        rows.append([label, f"{passes.pop():,}",
                     ms(canon[key]['median_of_medians']) if key else '---',
                     ms(arm[key]['median_ms']) if key else '---',
                     ms_or_s(nrf[op]['ms_median']), ms_or_s(stm[op]['ms_median'])])
    return ['Method', 'Passes', 'x86 EPYC', 'ARM V1', 'nRF52840 64 MHz', 'STM32L4 16 MHz'], rows


def cost_claims():
    canon = load(COST_RESULTS / 'tabular_canonical.json')
    bb = load(COST_RESULTS / 'bus_budget.json')
    caps = bb['captures']
    road = [v for k, v in caps.items() if k.startswith('ROAD/')]
    src = 'results/cost/bus_budget.json'
    claim('bus.road_captures', 'ROAD ambient captures used for the budget', len(road), src)
    claim('bus.frames', 'benign frames analysed (ROAD + HCRL)', sum(v['frames'] for v in caps.values()), src)
    fast = [v['id_fast_ms'] for v in caps.values()]
    claim('bus.id_fast_min', 'fastest periodic CAN ID, smallest median period', min(fast), src, 'ms')
    claim('bus.id_fast_max', 'fastest periodic CAN ID, largest median period', max(fast), src, 'ms')
    claim('bus.road_mean_gap', 'mean frame gap, ROAD (median of captures)', bb['summary']['bus_mean_ms']['ROAD_median'], src, 'ms')
    claim('bus.hcrl_mean_gap', 'mean frame gap, HCRL', bb['summary']['bus_mean_ms']['HCRL'], src, 'ms')
    claim('bus.road_peak_gap', 'gap in the busiest 10 ms window, ROAD', bb['summary']['bus_peak_ms']['ROAD_min'], src, 'ms')

    src = 'results/cost/tabular_canonical.json'
    tree = canon['SHAP (Tree, exact)']['median_of_medians']
    kern = canon['SHAP (Kernel, model-agnostic)']['median_of_medians']
    inf = canon['inference only (no XAI)']['median_of_medians']
    claim('cost.tree_pct_budget', "TreeSHAP, % of one ID's 10 ms budget", 100 * tree / 10, src, '%')
    claim('cost.kernel_x_budget', "KernelSHAP, multiple of the 10 ms budget", kern / 10, src, 'x')
    claim('cost.tree_x_bus_gap', 'TreeSHAP / ROAD mean frame gap', tree / bb['summary']['bus_mean_ms']['ROAD_median'],
          src + ', bus_budget.json', 'x')
    claim('cost.tree_x_inference', 'TreeSHAP / inference on the server', tree / inf, src, 'x')
    cvs = [v['cv_pct'] for v in canon.values()]
    claim('cost.cv_min', 'run-to-run CV of tabular latency, min', min(cvs), src, '%')
    claim('cost.cv_max', 'run-to-run CV of tabular latency, max', max(cvs), src, '%')
    spreads = [100 * (v['ratio_range'][1] / v['ratio_range'][0] - 1)
               for k, v in canon.items() if not k.startswith('inference')]
    claim('cost.ratio_spread_min', 'run-to-run spread of the ratio to inference, min', min(spreads), src, '%')
    claim('cost.ratio_spread_max', 'run-to-run spread of the ratio to inference, max', max(spreads), src, '%')

    n400 = {r['method']: r for r in load(COST_RESULTS / 'vision_n400.json')['results']}
    src = 'results/cost/vision_n400.json'
    claim('cost.gradcam_n400_median', 'Grad-CAM median, n=400 run', n400['Grad-CAM']['median_ms'], src, 'ms')
    claim('cost.gradcam_n400_p99', 'Grad-CAM p99, n=400 run', n400['Grad-CAM']['p99_ms'], src, 'ms')
    gcb = load(COST_RESULTS / 'gradcam_boundary.json')
    claim('cost.gradcam_warm_median', 'Grad-CAM median, n=400 run with 50 warm-ups', gcb['median'], 'results/cost/gradcam_boundary.json', 'ms')
    claim('cost.gradcam_warm_p99', 'Grad-CAM p99, n=400 run with 50 warm-ups', gcb['p99'], 'results/cost/gradcam_boundary.json', 'ms')
    claim('cost.inference_n400_median', 'inference median, n=400 run', n400['inference only (no XAI)']['median_ms'], src, 'ms')

    mv = load(COST_RESULTS / 'model_validation.json')['rows']
    arm_mv = load(COST_RESULTS / 'arm-neoverse-v1/model_validation.json')['rows']
    src = 'results/cost/arm-neoverse-v1/model_validation.json'
    unc = [abs(r['error_pct']) for r in arm_mv if not r.get('calibration')]
    claim('arm.pred_median_err', 'ARM: median |error| on six uncalibrated points', st.median(unc), src, '%')
    claim('arm.pred_max_err', 'ARM: max |error| on six uncalibrated points', max(unc), src, '%')
    claim('arm.occl_max_err', 'ARM: max |error| on the three occlusion points',
          max(abs(r['error_pct']) for r in arm_mv if r['family'] == 'occlusion'), src, '%')
    claim('arm.ig_min_err', 'ARM: IG prediction error, most negative (overestimate)',
          min(r['error_pct'] for r in arm_mv if r['family'] == 'integrated_gradients'), src, '%')
    claim('x86.ig_max_err', 'x86: IG prediction error, largest (underestimate)',
          max(r['error_pct'] for r in mv if r['family'] == 'integrated_gradients'),
          'results/cost/model_validation.json', '%')
    ig = {r['param']: r for r in mv if r['family'] == 'integrated_gradients'}
    g1 = 100 * ((ig[50]['measured_ms'] / 50) / (ig[5]['measured_ms'] / 5) - 1)
    ov = {r['n_steps']: r for r in load(COST_RESULTS / 'ig_overhead.json')}
    g2 = 100 * ((ov[50]['ig_ms'] / 50) / (ov[5]['ig_ms'] / 5) - 1)  # integrated gradients itself
    claim('x86.ig_batch_growth_min', 'per-pass cost growth N=5 -> 50 with gradients, lower (ig_overhead.json)',
          min(g1, g2), 'results/cost/ig_overhead.json, model_validation.json', '%')
    claim('x86.ig_batch_growth_max', 'per-pass cost growth N=5 -> 50 with gradients, upper (model_validation.json)',
          max(g1, g2), 'results/cost/ig_overhead.json, model_validation.json', '%')

    arm = {r['method']: r for r in load(COST_RESULTS / 'arm-neoverse-v1/tabular_c7g.json')['results']}
    n1 = {r['method']: r for r in load(COST_RESULTS / 'arm-neoverse-n1/tabular_arm.json')['results']}
    moves = [100 * abs(arm[k]['median_ms'] / v['median_of_medians'] - 1) for k, v in canon.items()]
    src = 'results/cost/arm-neoverse-v1/tabular_c7g.json, tabular_canonical.json'
    claim('arm.latency_move_min', 'x86 -> ARM V1 latency change, smallest', min(moves), src, '%')
    claim('arm.latency_move_max', 'x86 -> ARM V1 latency change, largest', max(moves), src, '%')
    same = all(arm[k]['model_rows_per_explanation'] == v['passes'] == n1[k]['model_rows_per_explanation']
               for k, v in canon.items())
    claim('arm.passes_identical', 'pass counts identical on x86, Neoverse-V1 and Neoverse-N1 (1 = yes)',
          int(same), 'results/cost/arm-neoverse-v1/, arm-neoverse-n1/')


def mcu_claims():
    nrf = load(MCU_RESULTS / 'xai-nrf52840-r1/analysis.json')
    l475 = load(MCU_RESULTS / 'xai-st-iotnode-r1/analysis.json')
    l476 = load(MCU_RESULTS / 'xai-nucleo-l476rg/analysis.json')
    canon = load(COST_RESULTS / 'tabular_canonical.json')
    boards = {'nRF52840': nrf, 'STM32L475': l475, 'STM32L476': l476}
    src = 'results/mcu/*/analysis.json'
    claim('mcu.max_err_margin', 'max |margin - reference| over boards',
          max(b['correctness']['max_abs_err_margin'] for b in boards.values()), src)
    claim('mcu.max_err_treeshap', 'max |TreeSHAP - reference| over boards',
          max(b['correctness']['max_abs_err_treeshap'] for b in boards.values()), src)
    claim('mcu.checked_samples', 'test samples checked per board (min)',
          min(b['correctness']['checked'] for b in boards.values()), src)
    for name, b in (('nrf', nrf), ('stm', l476)):
        o = b['ops']
        claim(f'mcu.{name}.tree_x_deadline', f'{name}: TreeSHAP / 10 ms deadline', o['treeshap']['ms_median'] / 10, src, 'x')
        claim(f'mcu.{name}.tree_x_inference', f'{name}: TreeSHAP / inference', o['treeshap']['ms_median'] / o['infer_test']['ms_median'], src, 'x')
        claim(f'mcu.{name}.kernel_x_tree', f'{name}: KernelSHAP / TreeSHAP', o['kernel2096']['ms_median'] / o['treeshap']['ms_median'], src, 'x')
        eq = b['eq1']
        errs = [v['err_pct'] for k, v in eq.items() if isinstance(v, dict) and 'err_pct' in v]
        claim(f'mcu.{name}.eq1_err_min', f'{name}: Eq. (1) error with t_pass from inference, min', min(errs), src, '%')
        claim(f'mcu.{name}.eq1_err_max', f'{name}: Eq. (1) error with t_pass from inference, max', max(errs), src, '%')
        sm = [v['err_pct'] for k, v in eq['same_method'].items() if isinstance(v, dict)]
        claim(f'mcu.{name}.eq1_same_method_err', f'{name}: Eq. (1) error calibrated within KernelSHAP (N=2,101), worst',
              min(sm), src, '%')
    claim('mcu.cv_max', 'run-to-run CV of cycles, max over boards and methods',
          max(r['cyc_cv_pct'] for b in boards.values() for r in b['ops'].values()), src, '%')
    claim('mcu.l475_vs_l476_max_cycles', 'STM32L475 (IoT-LAB) vs STM32L476 (bench), max cycle difference',
          max(abs(l475['ops'][k]['cyc_median'] - l476['ops'][k]['cyc_median']) for k in l476['ops']), src, 'cycles')
    claim('mcu.kernel_cycles_stm', 'KernelSHAP cycles on the STM32L4', l476['ops']['kernel2096']['cyc_median'], src, 'cycles')
    mw = [r['mW_median'] for k, r in nrf['ops'].items() if k != 'spin1s']
    src = 'results/mcu/xai-nrf52840-r1/analysis.json'
    claim('mcu.power_min', 'nRF52840 board power, lowest method', min(mw), src, 'mW')
    claim('mcu.power_max', 'nRF52840 board power, highest method', max(mw), src, 'mW')
    claim('mcu.power_idle', 'nRF52840 board power, idle spin loop', nrf['ops']['spin1s']['mW_median'], src, 'mW')
    claim('mcu.energy_tree', 'energy of one TreeSHAP explanation', nrf['ops']['treeshap']['uJ_median'] / 1000, src, 'mJ')
    claim('mcu.energy_kernel', 'energy of one KernelSHAP explanation', nrf['ops']['kernel2096']['uJ_median'] / 1e6, src, 'J')


# ------------------------------------------------------------- CAN
def collapse_groups(key='precise'):
    rows = load(CAN_RESULTS / 'collapse_full.json')[key]['rows']
    held = [r for r in rows if not r['train']]
    same = [r for r in held if r['same_id']]
    new = [r for r in held if not r['same_id']]
    return same, new


@table('tab_collapse', 'Table: held-out transfer across attack modality (ROAD, per-frame labels)',
       ['results/can/collapse_full.json', 'results/can/drift.json', 'results/can/label_stats.json'])
def tab_collapse():
    drift = load(CAN_RESULTS / 'drift.json')
    ls = load(CAN_RESULTS / 'label_stats.json')
    same, new = collapse_groups('precise')
    wsame, wnew = collapse_groups('window')
    med = lambda g, k: st.median(r[k] for r in g)
    feats = drift['feats']
    attr = drift['attr_fab']
    alt = lambda kind: (sum(r['alternating_pairs'] for r in ls[kind])
                        / sum(r['pairs'] for r in ls[kind]))
    rows = [
        ['Same CAN ID as training', str(len(same)), f3(med(same, 'fab')), f3(med(same, 'mas'))],
        ['single-threshold rule, same ID', '', f3(drift['baseline_one_rule']['fab']), f3(drift['baseline_one_rule']['mas'])],
        ['CAN ID never seen', str(len(new)), f3(med(new, 'fab')), f3(med(new, 'mas'))],
        ['on bytes_changed', '', pct(attr[feats.index('bytes_changed')]), ''],
        ['on payload features, total', '', pct(1 - drift['timing_mass']['fab']), ''],
        ['label alternation between frames', '', pct(alt('fabrication'), 0), pct(alt('masquerade'), 0)],
        ['explanation drift (L1)', '', f3(drift['l1_drift']), ''],
        ['window labels: same / unseen CAN ID', f"{len(wsame)} / {len(wnew)}",
         f"{f3(med(wsame, 'fab'))} / {f3(med(wnew, 'fab'))}",
         f"{f3(med(wsame, 'mas'))} / {f3(med(wnew, 'mas'))}"],
    ]
    return ['Held-out group', 'n', 'F1 fabr.', 'F1 masq.'], rows


@table('fig_collapse', 'Figure: held-out F1 by capture, fabrication vs masquerade',
       ['results/can/collapse_full.json'])
def fig_collapse():
    rows = load(CAN_RESULTS / 'collapse_full.json')['precise']['rows']
    order = ['max_speedometer_attack_3', 'reverse_light_off_attack_3', 'reverse_light_on_attack_3',
             'max_engine_coolant_temp_attack', 'correlated_signal_attack_1',
             'correlated_signal_attack_2', 'correlated_signal_attack_3']
    by = {r['base']: r for r in rows}
    return ['Capture', 'CAN ID', 'F1 fabrication', 'F1 masquerade'], \
        [[b, by[b]['id'], f3(by[b]['fab']), f3(by[b]['mas'])] for b in order]


@table('fig_attribution', 'Figure: SHAP attribution mass per feature, fabrication vs masquerade',
       ['results/can/drift.json'])
def fig_attribution():
    d = load(CAN_RESULTS / 'drift.json')
    feats, a, b = d['feats'], d['attr_fab'], d['attr_mas']
    show = ['bytes_changed', 'delta_same_id', 'id_count_win', 'period_dev',
            'bus_rate_win', 'byte4', 'hamming_prev', 'byte6']
    top8 = sorted(range(len(feats)), key=lambda j: -a[j])[:8]
    assert [feats[j] for j in top8] == show, [feats[j] for j in top8]
    rows = [[feats[j], f"{100 * a[j]:.1f}", f"{100 * b[j]:.1f}"] for j in top8]
    rows.append(['L1 drift', f3(d['l1_drift']), ''])
    return ['Feature', 'Fabrication %', 'Masquerade %'], rows


def importance_from_log():
    """Gain-importance shares printed by cross_vehicle.py (not stored in its JSON)."""
    txt = (CAN_RESULTS / 'cross_vehicle.log').read_text()
    out = {}
    for who in ('HCRL', 'ROAD'):
        line = re.search(rf"{who} model looks at: (.*)", txt).group(1)
        out[who] = {f: int(v) for f, v in re.findall(r"(\w+)\((\d+)%\)", line)}
    prev = {'ROAD_test': [float(v) for v in re.findall(
        r"(?:max_speedometer|reverse_light_off|reverse_light_on)_attack_3 +\d+ rows +([\d.]+)% attack", txt)],
        'HCRL': [float(v) for v in re.findall(r"HCRL \w+ +\d+ rows +([\d.]+)% attack", txt)]}
    return out, prev


@table('tab_transfer', 'Table: transfer across vehicle and attack modality',
       ['results/can/cross_vehicle.json', 'results/can/cross_vehicle.log',
        'results/can/drift.json', 'results/can/cross_family.json'])
def tab_transfer():
    cv = load(CAN_RESULTS / 'cross_vehicle.json')
    drift = load(CAN_RESULTS / 'drift.json')
    fam = load(CAN_RESULTS / 'cross_family.json')
    imp, _ = importance_from_log()
    r = lambda d: [f3(d['f1']), f3(d['recall']), f4(d['fpr'])]
    rows = [
        ['HCRL -> HCRL', '=', '='] + r(cv['HCRL -> HCRL (held-out)']),
        ['ROAD -> ROAD', '=', '='] + r(cv['ROAD -> ROAD fabrication']),
        ['HCRL -> ROAD', '!=', '='] + r(cv['HCRL -> ROAD fabrication']),
        ['ROAD -> HCRL', '!=', '='] + r(cv['ROAD -> HCRL']),
        # target-ID evaluation of the detector of drift_experiment.py
        ['ROAD -> ROAD masq.', '=', '!='] + r(drift['perf']['masquerade']),
        ['HCRL -> ROAD masq.', '!=', '!='] + r(cv['HCRL -> ROAD masquerade']),
    ]
    for x in fam['rows']:
        if x['condition'].startswith('diff vehicle'):
            a, b = x['train'].split()[0], x['test'].split()[0]
            rows.append([f"{x['family'].capitalize()}: {a} -> {b}", '!=', '='] + r(x))
    tm = cv['timing_mass']
    src = 'results/can/cross_vehicle.json, results/can/cross_vehicle.log'
    claim('can.timing_hcrl_model', 'gain importance on timing, HCRL-trained model', 100 * tm['hcrl_model'], src, '%')
    claim('can.bytes_changed_road_model', 'gain importance on bytes_changed, ROAD-trained model',
          float(imp['ROAD']['bytes_changed']), src, '%')
    return ['Train -> test', 'Veh.', 'Mod.', 'F1', 'Recall', 'FPR'], rows


def can_claims():
    drift = load(CAN_RESULTS / 'drift.json')
    sm = load(CAN_RESULTS / 'sanity_masq.json')
    ls = load(CAN_RESULTS / 'label_stats.json')
    src = 'results/can/label_stats.json'
    fr = [r['forged_frac'] for r in ls['fabrication']]
    claim('can.window_benign_min', 'window label: benign share of fabrication interval, min of 3', 100 * (1 - max(fr)), src, '%')
    claim('can.window_benign_max', 'window label: benign share of fabrication interval, max of 3', 100 * (1 - min(fr)), src, '%')
    src = 'results/can/sanity_masq.json'
    claim('can.masq_flagged', 'masquerade frames flagged by the fabrication model', sm['prediction']['flagged'], src)
    claim('can.masq_n', 'masquerade frames evaluated', sm['prediction']['n'], src)
    claim('can.masq_true_rate', 'true attack rate in masquerade captures', 100 * sm['prediction']['true_rate'], src, '%')
    claim('can.masq_trained_f1', 'F1 of a detector trained on masquerade', sm['masq_trained']['f1'], src)
    claim('can.masq_trained_payload', 'payload share of the masquerade-trained detector',
          100 * (1 - sm['masq_trained']['timing_mass']), src, '%')
    src = 'results/can/drift.json'
    claim('can.attr_magnitude_ratio', 'attribution mass ratio masquerade / fabrication', drift['attr_magnitude']['ratio'], src, 'x')
    feats = drift['feats']
    claim('can.bytes_changed_fab', 'bytes_changed share, fabrication', 100 * drift['attr_fab'][feats.index('bytes_changed')], src, '%')
    claim('can.bytes_changed_mas', 'bytes_changed share, masquerade', 100 * drift['attr_mas'][feats.index('bytes_changed')], src, '%')
    # IG paired overhead ratios (IG ms / pure-pass ms at each step count)
    ig_ov = load(COST_RESULTS / 'ig_overhead.json')
    src_ig = 'results/cost/ig_overhead.json'
    for entry in ig_ov:
        n = entry['n_steps']
        claim(f'cost.ig_ratio_{n}', f'IG/pure-pass ratio at {n} steps', entry['ratio'], src_ig)

    # Per-frame vs window label verdicts on same-ID held-out captures
    cf = load(CAN_RESULTS / 'collapse_full.json')
    src_cf = 'results/can/collapse_full.json'
    for kind in ('precise', 'window'):
        rows = cf[kind]['rows']
        for r in rows:
            if not r['train'] and r['same_id']:
                tag = kind[:3]  # 'pre' or 'win'
                claim(f'can.{tag}_fab_{r["id"]}_{r["base"]}',
                      f'{kind} F1 fabrication {r["id"]} {r["base"]}', r['fab'], src_cf)
                claim(f'can.{tag}_mas_{r["id"]}_{r["base"]}',
                      f'{kind} F1 masquerade {r["id"]} {r["base"]}', r['mas'], src_cf)

    claim('can.blindness_margin', 'structural-blindness margin, ambient reference',
          load(CAN_RESULTS / 'blindness.json')['margin'], 'results/can/blindness.json')
    _, prev = importance_from_log()
    src = 'results/can/cross_vehicle.log'
    claim('can.prev_road_min', 'whole-bus attack prevalence, ROAD test captures, min', min(prev['ROAD_test']), src, '%')
    claim('can.prev_road_max', 'whole-bus attack prevalence, ROAD test captures, max', max(prev['ROAD_test']), src, '%')
    claim('can.prev_hcrl_min', 'attack prevalence, HCRL captures, min', min(prev['HCRL']), src, '%')
    claim('can.prev_hcrl_max', 'attack prevalence, HCRL captures, max', max(prev['HCRL']), src, '%')
    fam = load(CAN_RESULTS / 'cross_family.json')
    src = 'results/can/cross_family.json'
    claim('can.family_within_min', 'same-family detectors within one vehicle, lowest F1',
          min(x['f1'] for x in fam['rows'] if x['condition'].startswith('same vehicle')), src)
    tm = fam['timing_mass']
    for k in ('hcrl_spoof', 'hcrl_fuzz', 'road_spoof', 'road_fuzz'):
        claim(f'can.family_timing_{k}', f'timing share (gain), {k}', 100 * tm[k], src, '%')
    dm = load(CAN_RESULTS / 'drift_metrics.json')['summary']['mmd']
    da = load(CAN_RESULTS / 'drift_metrics_ambient_ref.json')['summary']['mmd']
    claim('can.mmd_benign_max_trainref', 'MMD, benign captures, max (training reference)', max(dm['ambient']),
          'results/can/drift_metrics.json')
    claim('can.mmd_collapse_min_trainref', 'MMD at the collapse, min (training reference)', min(dm['target']),
          'results/can/drift_metrics.json')
    src = 'results/can/drift_metrics_ambient_ref.json'
    claim('can.mmd_collapse_min_benignref', 'MMD at the collapse, min (benign reference)', min(da['target']), src)
    claim('can.mmd_collapse_max_benignref', 'MMD at the collapse, max (benign reference)', max(da['target']), src)
    claim('can.mmd_fab_min_benignref', 'MMD on new fabrication, min (benign reference)', min(da['null']), src)
    claim('can.mmd_fab_max_benignref', 'MMD on new fabrication, max (benign reference)', max(da['null']), src)


METRICS = [('agg_l1', 'Aggregate L1'), ('rank_tau', 'Rank distance (1 - tau)'),
           ('ks_max', 'Max. per-feature KS'), ('mmd', 'MMD^2'), ('c2st_shap', 'C2ST (AUC)'),
           ('c2st_input', 'C2ST on inputs'), ('ks_score', 'KS on output')]


@table('tab_driftmetrics', 'Table: label-free drift metrics against the masquerade collapse',
       ['results/can/drift_metrics.json', 'results/can/drift_metrics_ambient_ref.json'])
def tab_driftmetrics():
    t = load(CAN_RESULTS / 'drift_metrics.json')['summary']
    a = load(CAN_RESULTS / 'drift_metrics_ambient_ref.json')['summary']
    span = lambda v: f"{f3(min(v))}-{f3(max(v))}"
    # AUROC of collapse captures against benign captures (ties count one half)
    auroc = lambda x: f"{sum((c > b) + 0.5 * (c == b) for c in x['target'] for b in x['ambient']) / (len(x['target']) * len(x['ambient'])):.2f}"
    rows = [[label, f3(max(t[k]['null'])), span(t[k]['ambient']), span(t[k]['target']), auroc(t[k]),
             span(a[k]['ambient']), span(a[k]['target']), auroc(a[k])]
            for k, label in METRICS]
    return ['Metric', 'Train ref: new fabr. (max)', 'benign', 'collapse', 'AUROC',
            'Benign ref: benign', 'collapse', 'AUROC'], rows


@table('tab_ota', 'Table: explanation drift between model versions',
       ['results/can/ota_drift.json'])
def tab_ota():
    v = load(CAN_RESULTS / 'ota_drift.json')['versions']
    row = lambda x: [f3(x['f1_val_precise']), f3(x['f1_val_window']), f3(x['f1_masquerade'])]
    dom = lambda x: f"{x['top3'][0]} ({x['top3_share'][0]:.2f})"
    ra, rb = v['v1_retrain_a'], v['v1_retrain_b']
    retrain = [rng(ra['f1_val_precise'], rb['f1_val_precise']),
               rng(ra['f1_val_window'], rb['f1_val_window']),
               rng(ra['f1_masquerade'], rb['f1_masquerade']),
               rng(ra['expl_drift_l1_vs_v1'], rb['expl_drift_l1_vs_v1']),
               f"{ra['top3'][0]} ({rng(ra['top3_share'][0], rb['top3_share'][0], lambda s: f'{s:.2f}')})"]
    rows = [['Certified (v1)'] + row(v['v1']) + ['---', dom(v['v1'])],
            ['Retrain, same recipe'] + retrain,
            ['Coverage update'] + row(v['v2a']) + [f"{v['v2a']['expl_drift_l1_vs_v1']:.2f}", dom(v['v2a'])],
            ['Shortcut update'] + row(v['v2b']) + [f"{v['v2b']['expl_drift_l1_vs_v1']:.2f}", dom(v['v2b'])]]
    return ['Version', 'F1 frame', 'F1 window', 'F1 masq.', 'Drift L1', 'Dominant feature'], rows


# ------------------------------------------------------------- driver
def render(title, sources, header, rows):
    cols = [header] + rows
    w = [max(len(str(r[i])) if i < len(r) else 0 for r in cols) for i in range(len(header))]
    line = lambda r: '  '.join(str(c).ljust(w[i]) for i, c in enumerate(r)).rstrip()
    out = [title, 'source: ' + ', '.join(sources), '', line(header), '-' * (sum(w) + 2 * len(w))]
    out += [line(r) for r in rows]
    return '\n'.join(out) + '\n'


def build():
    """All tables and claims as plain data."""
    CLAIMS.clear()
    tables = {}
    for name, (title, sources, fn) in TABLES.items():
        header, rows = fn()
        tables[name] = {'title': title, 'sources': sources, 'header': header, 'rows': rows}
    cost_claims()
    mcu_claims()
    can_claims()
    return tables, list(CLAIMS)


def main():
    only = sys.argv[1:]
    tables, claims = build()
    OUT.mkdir(exist_ok=True)
    for name, t in tables.items():
        txt = render(t['title'], t['sources'], t['header'], t['rows'])
        (OUT / f'{name}.txt').write_text(txt)
        if not only or name in only:
            print(f"== {name}\n{txt}")
    if not only or 'claims' in only:
        print("== claims (numbers quoted in the text)")
        for c in claims:
            v = c['value']
            vs = f"{v:,.4g}" if isinstance(v, float) else f"{v:,}"
            print(f"  {c['id']:<34} {vs:>12} {c['unit']:<6} {c['text']}")
    (OUT / 'paper_numbers.json').write_text(json.dumps({'tables': tables, 'claims': claims}, indent=1))
    print(f"-> {OUT.relative_to(ROOT)}/")


if __name__ == '__main__':
    main()
