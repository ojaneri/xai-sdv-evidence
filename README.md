# What Explanations Cost and When They Fail: code and data

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23749400.svg)](https://doi.org/10.5281/zenodo.23749400)

This repository reproduces the measurements of the paper *What Explanations
Cost and When They Fail: Measuring XAI Evidence for Software-Defined Vehicles*.
It covers two questions. First, what an explanation costs: latency and model
passes of TreeSHAP, KernelSHAP, LIME, occlusion, Grad-CAM and Integrated
Gradients on x86 and ARM servers and on three Cortex-M4 microcontrollers, and a
cost model `T = N * t_pass(N)` that predicts it. Second, whether explanations
detect a detector failure: a CAN intrusion detector trained on the ROAD dataset
collapses from F1 1.000 to 0.000 when the attack modality changes and does not
transfer between vehicles (ROAD and HCRL), while explanation drift and other
label-free drift metrics do not flag the collapse.

The cost measurements of the tabular regime (`src/cost/xai_cost.py`, `src/mcu/`)
use an XGBoost model (200 trees, depth 6) trained on 24 synthetic features from
`sklearn.datasets.make_classification`, sized like a CAN IDS. It is not the CAN
detector of `src/can_ids/`, which uses 16 features computed from real frames.

## Requirements

- Python 3.12 and the packages in `requirements.txt` (CPU-only PyTorch is enough).
- GNU make; gcc for the host check of the C port (tier 3).
- Tier 2: about 4 GB of disk for the ROAD and HCRL datasets.
- Tier 3: accounts on Shepherd Nova and FIT IoT-LAB, or a NUCLEO-L476RG board.

```bash
python3 -m venv .venv
.venv/bin/pip install torch==2.12.0 torchvision==0.27.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -r requirements.txt
```

A `Dockerfile` with the same environment is included (`docker build -t xai-sdv-evidence .`;
the default command runs tier 1).

## Quick start

```bash
make smoke  PY=.venv/bin/python    # import and consistency checks (data checks skip without ROAD)
make tables PY=.venv/bin/python    # print every table and figure from results/, write out/
make verify PY=.venv/bin/python    # compare them with the numbers printed in the paper
```

`make verify` compares 330 values (every table cell and figure coordinate, and
the numbers quoted in the text) and ends with
`330 values match the paper, 0 noted presentation differences, 0 mismatches`.

## Paper item to command, script and result

Tier 1 regenerates every item below from the saved results with `make tables`
(one item: `PY=... python -m report.tables tab_cost`, etc.). The script column
is what produced the result file; its `make` target re-runs it (tier 2 or 3).

| Paper item | `report.tables` name | Producing script (`make` target) | Result files |
|---|---|---|---|
| Table: Cost of one explanation on the server | `tab_cost` | `src/cost/xai_cost.py` x4 + `src/cost/aggregate_runs.py` (`cost-tabular`); `src/cost/xai_cost_vision.py` (`cost-vision`, `cost-vision-n400`); `src/cost/gradcam_boundary.py` (`cost-gradcam`) | `results/cost/tabular_canonical.json`, `tabular_x86_p99.json`, `vision.json`, `vision_n400.json`, `gradcam_boundary.json` |
| Figure: prediction error of the cost model | `fig_cost_model` | `src/cost/validate_model.py` (`cost-model`) | `results/cost/model_validation.json` |
| Table: The same explanation on four processors | `tab_platforms` | as above; `src/cost/run_on_arm.sh` (ARM); `src/mcu/analyze.py` (MCUs) | `results/cost/tabular_canonical.json`, `results/cost/arm-neoverse-v1/tabular_c7g.json`, `results/mcu/xai-nrf52840-r1/analysis.json`, `results/mcu/xai-nucleo-l476rg/analysis.json` |
| Section Cost of evidence, text: CAN budgets (10 ms per ID, 0.42/0.51 ms mean gap, 0.23 ms peak) | claims `bus.*`, `cost.*` | `src/cost/bus_budget.py` (`bus-budget`) | `results/cost/bus_budget.json` |
| Section Cost of evidence, text: ARM portability (latency moves 12-20%, pass counts identical, 3.5% / 7.0% prediction error) | claims `arm.*` | `src/cost/run_on_arm.sh` | `results/cost/arm-neoverse-v1/`, `results/cost/arm-neoverse-n1/` |
| Section Cost of evidence, text: batch effect of IG (20-39%, x86 +42.5% vs ARM -7.0%, measured minus predicted), Grad-CAM n=400 | claims `x86.*`, `cost.gradcam_*` | `src/cost/ig_overhead.py` (`cost-ig`), `src/cost/validate_model.py`, `src/cost/xai_cost_vision.py` | `results/cost/ig_overhead.json`, `model_validation.json`, `vision_n400.json` |
| Section On microcontroller silicon, text (TreeSHAP 166 ms / 520 ms, Eq. (1) errors, energy, determinism) | claims `mcu.*` | `src/mcu/xai_fw.c` on the boards, `src/mcu/analyze.py` (`mcu-analyze`) | `results/mcu/*/analysis.json`, console logs, `results/mcu/ref.json` |
| Table: Held-out transfer across attack modality | `tab_collapse` | `src/can_ids/collapse_full.py` (`can-collapse`), `drift_experiment.py` (`can-drift`), `label_stats.py` (`can-labels`) | `results/can/collapse_full.json`, `drift.json`, `label_stats.json` |
| Figure: held-out transfer by CAN ID | `fig_collapse` | `src/can_ids/collapse_full.py` | `results/can/collapse_full.json` |
| Section Explanation evidence under shift, text (2 of 20,895 flagged, F1 0.966 trained on masquerade) | claims `can.*` | `src/can_ids/sanity_masq.py` (`can-sanity`) | `results/can/sanity_masq.json` |
| Table: Transfer across vehicle and attack modality | `tab_transfer` | `src/can_ids/cross_vehicle.py` (`can-cross-vehicle`), `cross_family.py` (`can-cross-family`), `drift_experiment.py` | `results/can/cross_vehicle.json`, `cross_vehicle.log`, `cross_family.json`, `drift.json` |
| Section Explanation evidence under shift, text: CAN IDs shared by the two vehicles (3 of 27 and 106) | none (tier 2 only) | `src/can_ids/id_overlap.py` (`can-ids`) | `results/can/id_overlap.json` |
| Table: Label-free drift metrics | `tab_driftmetrics` | `src/can_ids/drift_metrics.py` (`can-drift-metrics`) | `results/can/drift_metrics.json`, `drift_metrics_ambient_ref.json` |
| Table: Explanation drift between model versions | `tab_ota` | `src/can_ids/ota_drift.py` (`can-ota`) | `results/can/ota_drift.json` |

Where a number comes from, when it is not obvious:

- `tab_cost`, tabular rows: medians are the median of four x86 runs
  (`tabular_canonical.json`). The per-run JSON files were not kept, so the
  tabular p99 values are recorded in `tabular_x86_p99.json`.
- `tab_cost`, perception rows: medians and p99 from one run, `vision.json`
  (inference n=300, Grad-CAM n=100); pass counts from `vision_n400.json`
  (`vision.json` predates counting images instead of module calls). The Grad-CAM
  median and p99 quoted in the text (85.7 ms, 205 ms) are from `vision_n400.json`.
- `tab_transfer`, row ROAD to ROAD masquerade: the detector of
  `drift_experiment.py` evaluated on the attacked CAN ID (`perf.masquerade` in
  `drift.json`); the whole-bus evaluation is `perf_whole_bus`.
- `tab_transfer`, importance shares: gain importance printed by
  `cross_vehicle.py` and kept in `cross_vehicle.log`.
- `results/cost/arm-neoverse-n1/tabular_arm.json`: run on an AWS t4g
  (Graviton2, Neoverse-N1). Its `platform` field is a fixed string written by an
  earlier version of `xai_cost.py`, which now detects the CPU. The instance is
  burstable, so only its pass counts are used.

## Tier 1: regenerate tables and figures (minutes)

`make tier1` runs `smoke`, `tables` and `verify`. Nothing is trained and no
dataset is needed. Output goes to `out/` (one text file per table or figure and
`out/paper_numbers.json`).

## Tier 2: recompute from the public datasets (hours)

The datasets are not redistributed. Download and verify them into `data/`, or
set `XAI_SDV_DATA` to an existing copy:

```bash
make data-road    # ROAD, Zenodo record 10462796, 557 MB, CC BY 4.0
make data-hcrl    # HCRL Car-Hacking, about 950 MB, from its publisher
make smoke        # now also runs the 9 data checks (about 1 min)
```

Then run the targets of the table above, or all of them with `make tier2`.
Each script overwrites its file under `results/`, so `git diff results/` shows
what changed and `make verify` re-checks the paper. The ROAD parser is pure
Python, so the CAN targets take from a few minutes (`can-labels`, about 3 min)
to an hour or more each; the cost targets take minutes to tens of minutes.

- The CAN experiments use fixed seeds throughout, so they are expected to
  reproduce `results/can/` exactly.
- The cost experiments measure latency, so their milliseconds change with the
  machine and its load; their pass counts do not. `src/cost/run_on_arm.sh`
  repeats the cost bench on a remote ARM host. Use a host with dedicated cores.

Prevalence and labels: ROAD supplies the injected payload as a byte mask, and
every CAN experiment labels frames individually from it. The interval-level window label
(every frame in the injection interval is an attack) is
50% benign among target-ID frames under fabrication (`results/can/label_stats.json`); it is reported
alongside for comparison.

## Tier 3: microcontrollers (optional)

The tabular model and its explainers are ported to C (`src/mcu/xai_core.c`)
and run bare-metal by `src/mcu/xai_fw.c`, which prints one line per timed block
(`B r=<round> op=<method> reps=<n> passes=<N> cyc=<cycles>`) and the margins and
TreeSHAP values of 16 test samples for checking against `results/mcu/ref.json`.

Host check, no hardware needed:

```bash
make mcu-host      # rebuilds src/mcu/model.h and results/mcu/ref.json, checks the C port
make mcu-analyze   # re-derives the STM32L4 analyses from the saved console logs into build/mcu/
```

`mcu-host` regenerates `ref.json` byte for byte; `mcu-analyze` reproduces both
STM32L4 `analysis.json` files exactly (apart from the `source` path).

Prebuilt binaries in `firmware/`:

| Board | Binary | How it was run |
|---|---|---|
| nRF52840 at 64 MHz, Shepherd Nova | `xai_nrf52840.elf` | `make mcu-shepherd` (`src/mcu/shepherd_run.py`; needs `shepherd-client`), then `python -m mcu.analyze results/mcu/<run> --hz 64e6` on the downloaded HDF5 trace |
| STM32L475 at 16 MHz, FIT IoT-LAB st-iotnode | `xai_st-iotnode.elf` | `IOTLAB_USER=<login> make mcu-iotlab` (`src/mcu/iotlab_run.sh`; submit the .elf, one serial connection per node), then `python -m mcu.analyze results/mcu/<run>/raw_console.log --hz 16e6` |
| STM32L476 at 16 MHz, NUCLEO-L476RG | `xai_nucleo-l476rg.elf`, `.bin` | copy the `.bin` to the ST-LINK USB drive, `python -m mcu.serial_capture /dev/ttyACM0 results/mcu/<run>/raw.log`, press RESET, then `python -m mcu.analyze ... --hz 16e6` |

The binaries were built with arm-none-eabi-gcc 13.2.1,
`-O2 -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16`, inside the
pqm4 build tree: the nRF52840 build uses `src/mcu/nrf52840/` (startup and linker
script, bare metal), the STM32L4 builds use the pqm4 libopencm3 HAL with
`-DXAI_OCM3`. ELF debug sections were stripped afterwards, so the SHA-256 values
in `results/mcu/*/experiment.json` (taken before stripping) differ from the files
here; the loadable content is the same. The 439 MB Shepherd HDF5 trace of the
nRF52840 run is not included; its SHA-256 is in
`results/mcu/xai-nrf52840-r1/experiment.json`.

## Layout

```
src/common.py         data and results paths (XAI_SDV_DATA overrides data/)
src/smoke_test.py     import, consistency and ROAD pipeline checks
src/cost/             explanation cost: tabular and perception benches, cost-model
                      validation, IG overhead, Grad-CAM tail, CAN bus budgets,
                      run aggregation, remote ARM runner
src/can_ids/          ROAD/HCRL parsing and features, labelling, modality collapse,
                      sanity checks, blindness score, cross-vehicle and cross-family
                      transfer, drift metrics, OTA drift, dataset downloads
src/mcu/              C port and firmware, linker script and startup (nRF52840),
                      model export, host check, testbed runners, serial capture, analysis
src/report/           tier 1: tables and figures from results/, check against the paper
results/cost/         x86 and ARM cost measurements, bus budgets
results/can/          CAN experiment outputs
results/mcu/          per-board console logs, testbed metadata and analyses; ref.json
firmware/             prebuilt firmware that produced results/mcu/
```

## Data licences and citation

ROAD: Verma et al., CC BY 4.0, Zenodo record 10462796
(DOI 10.13139/ORNLNCCS/1728694). HCRL Car-Hacking: Hacking and Countermeasure
Research Lab, Korea University; cite Song, Woo and Kim, *Vehicular
Communications* 21, 100198, 2020, and Seo, Song and Kim, PST 2018. Neither
dataset is redistributed here.

Code: MIT (`LICENSE`). Documentation and result files: CC BY 4.0. To cite this
repository, see `CITATION.cff`.
