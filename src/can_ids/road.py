#!/usr/bin/env python3
"""Shared loading and labelling for the ROAD experiments.

Every CAN experiment builds its feature matrices through this module, so the
loading, labelling and row-selection rules are defined in exactly one place.
"""
from pathlib import Path
import json
import numpy as np
from can_ids import features as cf
from common import ROOT, DATA, CAN_RESULTS  # noqa: F401  (re-exported)

SEED = 20260823
ATTACKS = DATA / 'road' / 'attacks'
AMBIENT = DATA / 'road' / 'ambient'

TIMING_FEATS = ('delta_same_id', 'period_dev', 'id_count_win', 'bus_rate_win')
TIMING_IDX = [cf.FEATS.index(f) for f in TIMING_FEATS]


class _Metadata:
    """Lazily-loaded ROAD capture metadata.

    Loading is deferred so that importing this module never fails when the
    dataset is absent: the smoke test and the scripts that need no data must
    run on a fresh clone.
    """

    _data = None

    def _load(self):
        """Load and cache the metadata, with a message that says what to do."""
        if self._data is None:
            path = ATTACKS / 'capture_metadata.json'
            if not path.is_file():
                raise FileNotFoundError(
                    f"{path} not found. The ROAD dataset is not bundled with "
                    "this repository; fetch it with:\n"
                    "    make data-road")
            with open(path) as f:
                self._data = json.load(f)
        return self._data

    def __getitem__(self, k):
        """Metadata for one capture."""
        return self._load()[k]

    def __iter__(self):
        """Iterate capture names."""
        return iter(self._load())

    def __len__(self):
        """Number of captures with metadata."""
        return len(self._load())

    def __contains__(self, k):
        """Is this capture present in the metadata?"""
        return k in self._load()

    def get(self, k, default=None):
        """Metadata for one capture, or a default."""
        return self._load().get(k, default)

    def keys(self):
        """Capture names."""
        return self._load().keys()

    def available(self):
        """True when the dataset is present, without raising."""
        return (ATTACKS / 'capture_metadata.json').is_file()


def metadata():
    """ROAD capture metadata as a dict. Raises if the dataset is absent."""
    return META._load()


META = _Metadata()


def target_id(name):
    """CAN ID under attack, or None when the capture has no single target.

    accelerator_* have injection_id null and fuzzing_* have "XXX": those attacks
    do not aim at one ID. Callers must handle None rather than crash on
    int(None, 16).
    """
    raw = META[name].get('injection_id')
    if not raw or not raw.startswith('0x'):
        return None
    return int(raw, 16)


_PARSE_CACHE = {}
_CACHE_LIMIT = 16   # ~50 MB each; keeps the working set under ~800 MB


def _parsed(name):
    """Parse+extract once per capture per process.

    drift_experiment.py loads the same logs under two labelling modes and two
    row selections. Parsing is the bottleneck (pure-Python hex decode over
    ~10^6 lines); labelling and slicing are cheap, so each capture is parsed
    once and cached.
    """
    if len(_PARSE_CACHE) >= _CACHE_LIMIT and name not in _PARSE_CACHE:
        # ~50 MB per capture; 33 captures would be ~1.5 GB. Evict FIFO rather
        # than grow without bound, and say so instead of silently thrashing.
        victim = next(iter(_PARSE_CACHE))
        del _PARSE_CACHE[victim]
        print(f"   [cache] evicted {victim} (limit {_CACHE_LIMIT})")
    if name not in _PARSE_CACHE:
        msgs, stats = cf.parse_log(ATTACKS / f'{name}.log', want_stats=True)
        if stats['rejected_frac'] > 0.01:
            raise ValueError(
                f"{name}: {stats['rejected_frac']*100:.1f}% of lines unparsed "
                f"({stats['rejected']}/{stats['total']}). Refusing to build "
                "features from a log the parser does not understand.")
        X, ts = cf.extract(msgs)
        ids = np.array([m[1] for m in msgs])
        _PARSE_CACHE[name] = (msgs, X, ts, ids)
    return _PARSE_CACHE[name]


def load(name, only_target_id=True, min_rows=50, precise=True):
    """Features and labels for one capture.

    precise=True uses per-frame labels from ROAD's injection mask. The window
    label it replaces marks every frame in the interval as attack, which under
    fabrication is 50% benign traffic (measured; see label_stats.py)
    and teaches the model "this window is under attack" instead of "this frame
    is forged". precise=False reproduces the window label for comparison, which
    is what most published CAN IDS work uses.

    only_target_id=True restricts to the attacked ID. That is privileged
    information a real IDS does not have; it is the default because it isolates
    the modality variable, and only_target_id=False measures what it costs.

    Returns (None, None) when the capture cannot supply what was asked for.
    """
    tid = target_id(name)
    if only_target_id and tid is None:
        return None, None
    msgs, X, ts, ids = _parsed(name)
    if precise:
        mask = cf.injection_mask(META[name].get('injection_data_str'))
        if not mask or tid is None:
            return None, None
        y = cf.label_precise(msgs, ts, META[name]['injection_interval'], tid,
                             mask, capture=name)
    else:
        y = cf.label(ts, META[name]['injection_interval'], capture=name)
    if only_target_id:
        sel = ids == tid
    else:
        sel = np.ones(len(msgs), dtype=bool)
    if sel.sum() < min_rows:
        return None, None
    return X[sel], y[sel]


def load_many(names, only_target_id=True, verbose=False, precise=True,
              strict=True):
    """Stack several captures.

    Seven ROAD captures (accelerator_*, fuzzing_*) have no single target ID
    and no usable injection mask. Dropping them in silence would give a caller
    a smaller n than it believed it had, so `strict=True` raises and
    `strict=False` warns and continues.
    """
    Xs, ys, skipped = [], [], []
    for n in names:
        X, y = load(n, only_target_id=only_target_id, precise=precise)
        if X is None:
            skipped.append(n)
            continue
        Xs.append(X)
        ys.append(y)
        if verbose:
            print(f"   {n:<45} {len(X):>7} rows  {y.mean()*100:5.1f}% attack")
    if skipped:
        msg = (f"{len(skipped)} of {len(names)} captures unusable "
               f"(no target id or no injection mask): {', '.join(skipped)}")
        if strict:
            raise ValueError(msg + " -- pass strict=False to proceed with a "
                                   "smaller n, knowingly.")
        print(f"   WARNING: {msg}")
    if not Xs:
        return None, None
    return np.vstack(Xs), np.concatenate(ys)


def make_model(n_jobs=4):
    """The gradient-boosted classifier used throughout, with a fixed seed."""
    import xgboost as xgb
    return xgb.XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1, tree_method='hist',
        n_jobs=n_jobs, random_state=SEED, eval_metric='logloss')


def matched_pairs():
    """Base names that have both a fabrication and a masquerade capture."""
    return sorted(k.replace('_masquerade', '') for k in META
                  if k.endswith('_masquerade') and k.replace('_masquerade', '') in META)


def normalized_attribution(explainer, X, n=3000, rng_seed=SEED):
    """Mean |SHAP| per feature, normalized, with the magnitude kept.

    If the model is inert on a regime, sv.sum() approaches zero and the
    normalized vector is amplified numerical noise, which would make any L1
    comparison meaningless. The absolute magnitude is therefore returned so
    callers can check that the comparison is between two real distributions,
    not between noise.
    """
    idx = np.random.default_rng(rng_seed).choice(
        len(X), size=min(n, len(X)), replace=False)
    sv = np.abs(explainer.shap_values(X[idx])).mean(0)
    total = float(sv.sum())
    if total <= 1e-12:
        raise ValueError(
            "attribution mass is ~0; a normalized comparison would compare noise")
    return sv / total, total
